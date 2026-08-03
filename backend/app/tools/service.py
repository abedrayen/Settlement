from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.guardrails.engine import GuardrailEngine
from app.repositories.borrower import (
    BorrowerRepository,
    FrontierRepository,
    MonitoringRepository,
    PortfolioRepository,
)
from app.services.model_scorer import ModelScorer
from app.services.optimizer import OptimizerError, optimize_portfolio
from app.services.settings_store import load_guardrail_config


class ToolService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.borrower_repo = BorrowerRepository(session)
        self.portfolio_repo = PortfolioRepository(session)
        self.frontier_repo = FrontierRepository(session)
        self.monitoring_repo = MonitoringRepository(session)
        self.guardrails = GuardrailEngine(session)
        self.scorer = ModelScorer(session)

    async def borrower_lookup(self, customer_code: int | None = None, settlement_code: int | None = None) -> dict[str, Any]:
        start = time.perf_counter()
        if customer_code:
            profile = await self.borrower_repo.get_by_customer_code(customer_code)
        elif settlement_code:
            profile = await self.borrower_repo.get_by_settlement_code(settlement_code)
        else:
            return {"error": "customer_code or settlement_code required"}
        if not profile:
            return {"error": "Borrower not found"}
        legal_name = profile.customer.get("legal_name")
        result = {
            "customer_code": profile.customer_code,
            "legal_name": legal_name,
            "display_name": f"{legal_name} ({profile.customer_code})" if legal_name else str(profile.customer_code),
            "settlement_code": profile.settlement_code,
            "customer": profile.customer,
            "settlement": profile.settlement,
            "recommended_offer": profile.recommended,
            "accounts": profile.accounts,
        }
        return {"data": result, "duration_ms": int((time.perf_counter() - start) * 1000)}

    async def payment_history(self, customer_code: int) -> dict[str, Any]:
        start = time.perf_counter()
        profile = await self.borrower_repo.get_by_customer_code(customer_code)
        if not profile:
            return {"error": "Borrower not found", "duration_ms": int((time.perf_counter() - start) * 1000)}
        payments = await self.borrower_repo.get_payments(customer_code)
        legal_name = profile.customer.get("legal_name")
        return {
            "data": {
                "customer_code": customer_code,
                "legal_name": legal_name,
                "display_name": f"{legal_name} ({customer_code})" if legal_name else str(customer_code),
                **payments,
            },
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }

    async def offer_grid(self, customer_code: int) -> dict[str, Any]:
        start = time.perf_counter()
        grid = await self.borrower_repo.get_offer_grid(customer_code)
        profile = await self.borrower_repo.get_by_customer_code(customer_code)
        if not profile:
            return {"error": "Borrower not found", "duration_ms": int((time.perf_counter() - start) * 1000)}
        legal_name = profile.customer.get("legal_name")
        return {
            "data": {
                "grid": grid,
                "recommended": profile.recommended,
                "customer_code": customer_code,
                "legal_name": legal_name,
                "display_name": f"{legal_name} ({customer_code})" if legal_name else str(customer_code),
            },
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }

    async def offer_optimization(
        self,
        customer_code: int | None = None,
        max_rr: float | None = None,
        min_p_fulfill: float | None = None,
        fixed_installments: int | None = None,
        mode: str = "single",
        customer_codes: list[int] | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        cfg = load_guardrail_config()
        rr_min = float(cfg.get("rr_min", 0.20))
        rr_max = float(cfg.get("rr_max", 0.80))
        opt_cfg = cfg.get("optimizer") or {}

        if mode == "portfolio":
            offers = await self.borrower_repo.get_grid_by_customers(customer_codes)
            try:
                result = optimize_portfolio(
                    offers,
                    rr_min=rr_min,
                    rr_max=rr_max,
                    max_rr=max_rr,
                    min_p_fulfill=min_p_fulfill,
                    max_avg_rr=opt_cfg.get("max_avg_rr"),
                    max_installment_share=opt_cfg.get("max_installment_share", 0.6),
                    high_installment_threshold=int(opt_cfg.get("high_installment_threshold", 3)),
                )
            except OptimizerError as exc:
                return {"error": str(exc), "duration_ms": int((time.perf_counter() - start) * 1000)}
            return {"data": result, "duration_ms": int((time.perf_counter() - start) * 1000)}

        if customer_code is None:
            return {"error": "customer_code required for single mode", "duration_ms": int((time.perf_counter() - start) * 1000)}

        guard = await self.guardrails.evaluate(customer_code)
        if guard.status == "blocked":
            return {
                "blocked": True,
                "guardrails": guard.to_dict(),
                "duration_ms": int((time.perf_counter() - start) * 1000),
            }

        try:
            offer = await self.borrower_repo.optimize_offer(
                customer_code, max_rr, min_p_fulfill, fixed_installments, rr_min=rr_min, rr_max=rr_max
            )
        except OptimizerError as exc:
            return {"error": str(exc), "duration_ms": int((time.perf_counter() - start) * 1000)}

        if not offer:
            return {"error": "No feasible offer found", "duration_ms": int((time.perf_counter() - start) * 1000)}

        profile = await self.borrower_repo.get_by_customer_code(customer_code)
        legal_name = profile.customer.get("legal_name") if profile else None
        alternatives = await self.borrower_repo.top_grid_alternatives(customer_code, 3)
        decision = self.guardrails.classify_decision(guard, offer, legal_name=legal_name)

        if decision.get("requires_approval") and decision.get("approver_queue"):
            await self.guardrails.create_approval_task(
                customer_code=customer_code,
                settlement_code=profile.settlement_code if profile else 0,
                queue=decision["approver_queue"],
                reason=decision.get("approval_reason") or "RequiresApproval",
                risk_tier=decision.get("risk_tier"),
                decision_payload={**offer, **decision, "legal_name": legal_name},
            )

        return {
            "data": {
                **offer,
                "legal_name": legal_name,
                "display_name": f"{legal_name} ({customer_code})" if legal_name else str(customer_code),
                "alternatives": alternatives,
                **decision,
            },
            "guardrails": guard.to_dict(),
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }

    async def portfolio_analytics(self) -> dict[str, Any]:
        start = time.perf_counter()
        kpis = await self.portfolio_repo.get_kpis()
        segments = await self.portfolio_repo.get_segments()
        return {"data": {"kpis": kpis, "segments": segments}, "duration_ms": int((time.perf_counter() - start) * 1000)}

    async def frontier_analysis(
        self, min_p_fulfill: float | None = None, max_rr: float | None = None
    ) -> dict[str, Any]:
        start = time.perf_counter()
        frontier = await self.frontier_repo.get_frontier()
        try:
            optimization = await self.frontier_repo.optimize_under_constraints(min_p_fulfill, max_rr)
        except ValueError as exc:
            return {"error": str(exc), "duration_ms": int((time.perf_counter() - start) * 1000)}
        return {
            "data": {"frontier": frontier, "optimization": optimization},
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }

    async def monitoring(self) -> dict[str, Any]:
        start = time.perf_counter()
        metrics = await self.monitoring_repo.get_all()
        alerts = [m for m in metrics if m["alert_flag"]]
        return {"data": {"metrics": metrics, "alerts": alerts}, "duration_ms": int((time.perf_counter() - start) * 1000)}

    async def explainability(self, customer_code: int, model_name: str = "PoA_v3.1") -> dict[str, Any]:
        start = time.perf_counter()
        shap = await self.borrower_repo.get_shap(customer_code, model_name)
        profile = await self.borrower_repo.get_by_customer_code(customer_code)
        legal_name = profile.customer.get("legal_name") if profile else None
        positive = [s for s in shap if s["direction"] == "positive"][:3]
        negative = [s for s in shap if s["direction"] == "negative"][:3]
        return {
            "data": {
                "customer_code": customer_code,
                "legal_name": legal_name,
                "display_name": f"{legal_name} ({customer_code})" if legal_name else str(customer_code),
                "top_positive": positive,
                "top_negative": negative,
                "all": shap,
            },
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }

    async def model_score(
        self,
        customer_code: int,
        recovery_rate: float | None = None,
        installments: int | None = None,
        rescore_grid: bool = False,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            data = await self.scorer.score(
                customer_code,
                recovery_rate=recovery_rate,
                installments=installments,
                rescore_grid=rescore_grid,
            )
        except ValueError as exc:
            return {"error": str(exc), "duration_ms": int((time.perf_counter() - start) * 1000)}
        return {"data": data, "duration_ms": int((time.perf_counter() - start) * 1000)}

    async def installment_comparison(self, from_inst: int = 2, to_inst: int = 1, limit: int = 5) -> dict[str, Any]:
        start = time.perf_counter()
        results = await self.borrower_repo.compare_installments(from_inst, to_inst, limit)
        return {"data": results, "duration_ms": int((time.perf_counter() - start) * 1000)}

    async def create_handoff(
        self,
        customer_code: int | None,
        settlement_code: int | None,
        reason: str,
        conversation_id: UUID | None = None,
        legal_name: str | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        task = await self.guardrails.create_workflow_task(
            customer_code=customer_code,
            settlement_code=settlement_code,
            task_type="human_handoff",
            reason=reason[:100],
            queue="human_handoff",
            status="open",
            risk_tier="medium",
            conversation_id=conversation_id,
            decision_payload={"legal_name": legal_name, "customer_code": customer_code, "reason": reason},
        )
        return {
            "data": {
                "task_id": str(task.task_id),
                "status": task.status,
                "assigned_queue": task.assigned_queue,
                "customer_code": customer_code,
                "legal_name": legal_name,
                "display_name": f"{legal_name} ({customer_code})" if legal_name and customer_code else None,
            },
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }

    async def create_exception_request(
        self,
        customer_code: int,
        reason: str,
        conversation_id: UUID | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        profile = await self.borrower_repo.get_by_customer_code(customer_code)
        if not profile:
            return {"error": "Borrower not found", "duration_ms": int((time.perf_counter() - start) * 1000)}
        legal_name = profile.customer.get("legal_name")
        task = await self.guardrails.create_workflow_task(
            customer_code=customer_code,
            settlement_code=profile.settlement_code,
            task_type="exception_request",
            reason=reason[:100],
            queue="manager_approval",
            status="pending_approval",
            risk_tier="medium",
            conversation_id=conversation_id,
            decision_payload={"legal_name": legal_name, "customer_code": customer_code, "reason": reason},
        )
        return {
            "data": {
                "task_id": str(task.task_id),
                "status": task.status,
                "assigned_queue": task.assigned_queue,
                "customer_code": customer_code,
                "legal_name": legal_name,
                "display_name": f"{legal_name} ({customer_code})" if legal_name else str(customer_code),
            },
            "duration_ms": int((time.perf_counter() - start) * 1000),
        }
