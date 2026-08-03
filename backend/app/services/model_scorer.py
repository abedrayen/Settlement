"""Simulated on-demand ModelScorer (T5) — deterministic, not live .pkl inference."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.borrower import BorrowerRepository
from app.services.scoring import score_offer
from app.services.settings_store import get_model_versions

SEGMENT_FACTORS = {
    "Prime": 0.04,
    "Near-Prime": 0.02,
    "Subprime": -0.02,
    "Deep Subprime": -0.05,
}


class ModelScorer:
    def __init__(self, session: AsyncSession):
        self.repo = BorrowerRepository(session)

    def _segment_factor(self, segment: str | None) -> float:
        if not segment:
            return 0.0
        return SEGMENT_FACTORS.get(segment, 0.0)

    async def score(
        self,
        customer_code: int,
        recovery_rate: float | None = None,
        installments: int | None = None,
        rescore_grid: bool = False,
    ) -> dict[str, Any]:
        profile = await self.repo.get_by_customer_code(customer_code)
        if not profile:
            raise ValueError("Borrower not found")

        balance = float(profile.settlement.get("total_balance_connected_loans") or 0)
        segment = profile.customer.get("segment")
        legal_name = profile.customer.get("legal_name")
        seg_f = self._segment_factor(segment)
        versions = get_model_versions()
        active = next((v for v in versions if v.get("active")), versions[0] if versions else {})

        result: dict[str, Any] = {
            "customer_code": customer_code,
            "legal_name": legal_name,
            "display_name": f"{legal_name} ({customer_code})" if legal_name else str(customer_code),
            "balance": balance,
            "segment": segment,
            "model_versions": active,
            "scoring_mode": "simulated_deterministic",
        }

        if rescore_grid:
            grid = await self.repo.get_offer_grid(customer_code)
            rescored = []
            for row in grid:
                scored = score_offer(
                    customer_code,
                    balance,
                    float(row["recovery_rate"]),
                    int(row["installments"]),
                    seg_f,
                )
                rescored.append({**row, **scored, "stored_ev": row.get("expected_value")})
            rescored.sort(key=lambda r: r["expected_value"], reverse=True)
            result["grid"] = rescored
            result["best"] = rescored[0] if rescored else None
            return result

        rr = recovery_rate
        inst = installments
        if rr is None or inst is None:
            rec = profile.recommended or {}
            rr = float(rr if rr is not None else rec.get("optimal_rr") or 0.40)
            inst = int(inst if inst is not None else rec.get("optimal_installments") or 2)

        scored = score_offer(customer_code, balance, rr, inst, seg_f)
        result["offer"] = scored
        # Also expose stage labels matching product vocabulary
        result["PoAPP"] = scored["p_application"]
        result["PoA"] = scored["p_acceptance"]
        result["PoF"] = scored["p_fulfillment"]
        return result
