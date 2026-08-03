from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    BridgeMapping,
    DimCustomer,
    FactAccount,
    FactActivity,
    FactApplication,
    FactEfficientFrontier,
    FactModelMonitoring,
    FactOfferGridScore,
    FactPayment,
    FactPortfolioKpiMonthly,
    FactRecommendedOffer,
    FactSettlement,
    FactShapExplanation,
)


@dataclass
class BorrowerProfile:
    customer_code: int
    settlement_code: int
    account_code: int | None
    customer: dict[str, Any]
    settlement: dict[str, Any]
    recommended: dict[str, Any] | None
    accounts: list[dict[str, Any]]


class BorrowerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_customer_code(self, customer_code: int) -> BorrowerProfile | None:
        customer = await self.session.get(DimCustomer, customer_code)
        if not customer:
            return None

        bridge = (
            await self.session.execute(
                select(BridgeMapping).where(BridgeMapping.customer_code == customer_code)
            )
        ).scalar_one_or_none()

        settlement = None
        if bridge:
            settlement = await self.session.get(FactSettlement, bridge.settlement_code)

        rec = (
            await self.session.execute(
                select(FactRecommendedOffer).where(FactRecommendedOffer.customer_code == customer_code)
            )
        ).scalar_one_or_none()

        accounts = (
            await self.session.execute(
                select(FactAccount).where(FactAccount.customer_code == customer_code)
            )
        ).scalars().all()

        return BorrowerProfile(
            customer_code=customer_code,
            settlement_code=bridge.settlement_code if bridge else 0,
            account_code=bridge.account_code if bridge else None,
            customer=self._customer_dict(customer),
            settlement=self._settlement_dict(settlement) if settlement else {},
            recommended=self._rec_dict(rec) if rec else None,
            accounts=[self._account_dict(a) for a in accounts],
        )

    async def get_by_settlement_code(self, settlement_code: int) -> BorrowerProfile | None:
        bridge = await self.session.get(BridgeMapping, settlement_code)
        if not bridge:
            return None
        return await self.get_by_customer_code(bridge.customer_code)

    async def search(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        query = q.strip()
        if not query:
            return []
        if query.isdigit():
            profile = await self.get_by_customer_code(int(query))
            if not profile:
                return []
            return [
                {
                    "customer_code": profile.customer_code,
                    "legal_name": profile.customer.get("legal_name"),
                    "segment": profile.customer.get("segment"),
                    "settlement_status": profile.settlement.get("settlement_status"),
                }
            ]

        rows = (
            await self.session.execute(
                select(DimCustomer, FactSettlement.settlement_status)
                .outerjoin(BridgeMapping, BridgeMapping.customer_code == DimCustomer.customer_code)
                .outerjoin(FactSettlement, FactSettlement.settlement_code == BridgeMapping.settlement_code)
                .where(DimCustomer.legal_name.ilike(f"%{query}%"))
                .order_by(DimCustomer.legal_name)
                .limit(limit)
            )
        ).all()
        return [
            {
                "customer_code": c.customer_code,
                "legal_name": c.legal_name,
                "segment": c.segment,
                "settlement_status": status,
            }
            for c, status in rows
        ]

    async def list_customers(
        self,
        q: str | None = None,
        segment: str | None = None,
        status: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                DimCustomer,
                FactSettlement.settlement_status,
                FactSettlement.total_balance_connected_loans,
                FactRecommendedOffer.expected_value,
                FactRecommendedOffer.optimal_rr,
                FactRecommendedOffer.p_fulfillment,
            )
            .outerjoin(BridgeMapping, BridgeMapping.customer_code == DimCustomer.customer_code)
            .outerjoin(FactSettlement, FactSettlement.settlement_code == BridgeMapping.settlement_code)
            .outerjoin(FactRecommendedOffer, FactRecommendedOffer.customer_code == DimCustomer.customer_code)
        )
        if q and q.strip():
            query = q.strip()
            if query.isdigit():
                stmt = stmt.where(DimCustomer.customer_code == int(query))
            else:
                stmt = stmt.where(DimCustomer.legal_name.ilike(f"%{query}%"))
        if segment:
            stmt = stmt.where(DimCustomer.segment.ilike(segment))
        if status:
            stmt = stmt.where(FactSettlement.settlement_status.ilike(status))
        stmt = stmt.order_by(DimCustomer.legal_name).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "customer_code": c.customer_code,
                "legal_name": c.legal_name,
                "segment": c.segment,
                "settlement_status": settlement_status,
                "total_balance": total_balance,
                "expected_value": expected_value,
                "optimal_rr": optimal_rr,
                "p_fulfillment": p_fulfillment,
            }
            for c, settlement_status, total_balance, expected_value, optimal_rr, p_fulfillment in rows
        ]

    async def get_offer_grid(self, customer_code: int) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(FactOfferGridScore)
                .where(FactOfferGridScore.customer_code == customer_code)
                .order_by(FactOfferGridScore.recovery_rate, FactOfferGridScore.installments)
            )
        ).scalars().all()
        return [self._grid_dict(r) for r in rows]

    async def get_applications(self, customer_code: int) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                select(FactApplication).where(FactApplication.customer_code == customer_code).limit(5)
            )
        ).scalars().all()
        return {
            "count": len(rows),
            "latest_status": rows[0].application_status if rows else None,
            "latest_stage": rows[0].current_stage if rows else None,
        }

    async def get_payments(self, customer_code: int) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                select(FactPayment)
                .where(FactPayment.customer_code == customer_code)
                .order_by(FactPayment.payment_date.desc())
                .limit(12)
            )
        ).scalars().all()
        total = sum(r.payment_amount or 0 for r in rows)
        payments = [
            {
                "payment_date": r.payment_date.isoformat() if r.payment_date else None,
                "payment_amount": r.payment_amount,
                "payment_type": r.payment_type,
            }
            for r in rows
        ]
        return {
            "count_6m": len(rows),
            "total_6m": round(total, 2),
            "total": round(total, 2),
            "latest_date": rows[0].payment_date.isoformat() if rows and rows[0].payment_date else None,
            "payments": payments,
        }

    async def get_activities(self, customer_code: int) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                select(FactActivity)
                .where(FactActivity.customer_code == customer_code)
                .order_by(FactActivity.activity_date.desc())
                .limit(10)
            )
        ).scalars().all()
        return {
            "count": len(rows),
            "latest_type": rows[0].activity_type if rows else None,
            "latest_date": rows[0].activity_date.isoformat() if rows and rows[0].activity_date else None,
            "items": [
                {
                    "activity_date": r.activity_date.isoformat() if r.activity_date else None,
                    "activity_type": r.activity_type,
                    "contact_type": r.contact_type,
                    "outcome": r.outcome,
                }
                for r in rows
            ],
        }

    async def optimize_offer(
        self,
        customer_code: int,
        max_rr: float | None = None,
        min_p_fulfill: float | None = None,
        fixed_installments: int | None = None,
        rr_min: float = 0.20,
        rr_max: float = 0.80,
    ) -> dict[str, Any] | None:
        from app.services.optimizer import OptimizerError, optimize_single_borrower

        query = select(FactOfferGridScore).where(FactOfferGridScore.customer_code == customer_code)
        rows = (await self.session.execute(query)).scalars().all()
        if not rows:
            return None
        offers = [self._grid_dict(r) for r in rows]
        try:
            return optimize_single_borrower(
                offers,
                rr_min=rr_min,
                rr_max=rr_max,
                max_rr=max_rr,
                min_p_fulfill=min_p_fulfill,
                fixed_installments=fixed_installments,
            )
        except OptimizerError:
            raise

    async def get_grid_by_customers(
        self, customer_codes: list[int] | None = None
    ) -> dict[int, list[dict[str, Any]]]:
        query = select(FactOfferGridScore)
        if customer_codes:
            query = query.where(FactOfferGridScore.customer_code.in_(customer_codes))
        rows = (await self.session.execute(query)).scalars().all()
        by_customer: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            by_customer.setdefault(row.customer_code, []).append(self._grid_dict(row))
        return by_customer

    async def top_grid_alternatives(self, customer_code: int, limit: int = 3) -> list[dict[str, Any]]:
        grid = await self.get_offer_grid(customer_code)
        return sorted(grid, key=lambda r: r["expected_value"], reverse=True)[:limit]

    async def compare_installments(self, from_inst: int, to_inst: int, limit: int = 5) -> list[dict[str, Any]]:
        recs = (await self.session.execute(select(FactRecommendedOffer))).scalars().all()
        results = []
        for rec in recs:
            if rec.optimal_installments != from_inst:
                continue
            grid_from = (
                await self.session.execute(
                    select(FactOfferGridScore).where(
                        FactOfferGridScore.customer_code == rec.customer_code,
                        FactOfferGridScore.recovery_rate == rec.optimal_rr,
                        FactOfferGridScore.installments == from_inst,
                    )
                )
            ).scalar_one_or_none()
            grid_to = (
                await self.session.execute(
                    select(FactOfferGridScore).where(
                        FactOfferGridScore.customer_code == rec.customer_code,
                        FactOfferGridScore.recovery_rate == rec.optimal_rr,
                        FactOfferGridScore.installments == to_inst,
                    )
                )
            ).scalar_one_or_none()
            if grid_from and grid_to:
                delta = grid_to.expected_value - grid_from.expected_value
                if delta > 0:
                    results.append(
                        {
                            "customer_code": rec.customer_code,
                            "settlement_code": rec.settlement_code,
                            "recovery_rate": rec.optimal_rr,
                            "ev_from": grid_from.expected_value,
                            "ev_to": grid_to.expected_value,
                            "ev_delta": round(delta, 2),
                        }
                    )
        results.sort(key=lambda x: x["ev_delta"], reverse=True)
        return results[:limit]

    async def get_shap(self, customer_code: int, model_name: str = "PoA_v3.1") -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(FactShapExplanation)
                .where(
                    FactShapExplanation.customer_code == customer_code,
                    FactShapExplanation.model_name == model_name,
                )
                .order_by(FactShapExplanation.shap_value.desc())
            )
        ).scalars().all()
        return [
            {
                "feature_name": r.feature_name,
                "shap_value": r.shap_value,
                "direction": r.direction,
            }
            for r in rows
        ]

    def _customer_dict(self, c: DimCustomer) -> dict[str, Any]:
        return {
            "customer_code": c.customer_code,
            "legal_name": c.legal_name,
            "age": c.age,
            "segment": c.segment,
            "region": c.region,
            "occupation": c.occupation,
            "customer_type": c.customer_type,
            "aml_risk": c.aml_risk,
            "flag_deceased": c.flag_deceased,
            "flag_legal_entity": c.flag_legal_entity,
            "flag_under_law_protection": c.flag_under_law_protection,
            "vulnerability_status": c.vulnerability_status,
            "ood_flag": c.ood_flag,
        }

    def _settlement_dict(self, s: FactSettlement) -> dict[str, Any]:
        return {
            "settlement_code": s.settlement_code,
            "ref_year_month": s.ref_year_month,
            "portfolio_name": s.portfolio_name,
            "settlement_status": s.settlement_status,
            "settlement_amount": s.settlement_amount,
            "settlement_remaining_amount": s.settlement_remaining_amount,
            "settlement_nr_installments": s.settlement_nr_installments,
            "settlement_kept_percentage": s.settlement_kept_percentage,
            "settlement_type_description": s.settlement_type_description,
            "settlement_arrears_days": s.settlement_arrears_days,
            "total_balance_connected_loans": s.total_balance_connected_loans,
            "settlement_paid_amount": s.settlement_paid_amount,
            "assignment_channel_name": s.assignment_channel_name,
            "channel_group": s.channel_group,
            "days_from_last_activity": s.days_from_last_activity,
            "latest_activity_type": s.latest_activity_type,
            "right_party_contact_activities_3m": s.right_party_contact_activities_3m,
        }

    def _rec_dict(self, r: FactRecommendedOffer) -> dict[str, Any]:
        return {
            "optimal_rr": r.optimal_rr,
            "optimal_installments": r.optimal_installments,
            "expected_value": r.expected_value,
            "mip_gap": r.mip_gap,
            "model_version": r.model_version,
            "p_application": r.p_application,
            "p_acceptance": r.p_acceptance,
            "p_fulfillment": r.p_fulfillment,
        }

    def _account_dict(self, a: FactAccount) -> dict[str, Any]:
        return {
            "account_code": a.account_code,
            "total_balance": a.total_balance,
            "dpd": a.dpd,
            "bucket": a.bucket,
            "product": a.product,
            "business_unit": a.business_unit,
            "assignment_channel_name": a.assignment_channel_name,
            "channel_group": a.channel_group,
        }

    def _grid_dict(self, g: FactOfferGridScore) -> dict[str, Any]:
        return {
            "customer_code": g.customer_code,
            "settlement_code": g.settlement_code,
            "recovery_rate": g.recovery_rate,
            "installments": g.installments,
            "p_application": g.p_application,
            "p_acceptance": g.p_acceptance,
            "p_fulfillment": g.p_fulfillment,
            "expected_value": g.expected_value,
            "model_version": g.model_version,
        }


class PortfolioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_kpis(self) -> dict[str, Any]:
        total_ev = (
            await self.session.execute(select(func.sum(FactRecommendedOffer.expected_value)))
        ).scalar() or 0
        total_collections = (
            await self.session.execute(select(func.sum(FactSettlement.settlement_paid_amount)))
        ).scalar() or 0
        total_balance = (
            await self.session.execute(select(func.sum(FactSettlement.total_balance_connected_loans)))
        ).scalar() or 0
        borrower_count = (
            await self.session.execute(select(func.count(DimCustomer.customer_code)))
        ).scalar() or 0
        realization = round(total_collections / total_balance, 4) if total_balance else 0

        latest = (
            await self.session.execute(
                select(FactPortfolioKpiMonthly)
                .where(FactPortfolioKpiMonthly.segment == "All")
                .order_by(FactPortfolioKpiMonthly.ref_year_month.desc())
                .limit(2)
            )
        ).scalars().all()
        trend_delta = 0.0
        if len(latest) >= 2 and latest[0].realization_rate is not None and latest[1].realization_rate is not None:
            trend_delta = round((latest[0].realization_rate or 0) - (latest[1].realization_rate or 0), 4)
        elif latest and latest[0].realization_rate is not None:
            realization = latest[0].realization_rate or realization

        return {
            "total_expected_value": round(total_ev, 2),
            "total_collections": round(total_collections, 2),
            "total_outstanding_balance": round(total_balance, 2),
            "realization_rate": realization,
            "realization_trend_delta": trend_delta,
            "borrower_count": borrower_count,
            "ref_year_month": latest[0].ref_year_month if latest else "202606",
        }

    async def get_segments(self) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(
                    DimCustomer.segment,
                    func.count(DimCustomer.customer_code),
                    func.sum(FactRecommendedOffer.expected_value),
                    func.avg(FactRecommendedOffer.p_fulfillment),
                )
                .join(FactRecommendedOffer, DimCustomer.customer_code == FactRecommendedOffer.customer_code)
                .group_by(DimCustomer.segment)
            )
        ).all()
        return [
            {
                "segment": r[0],
                "borrower_count": r[1],
                "total_ev": round(r[2] or 0, 2),
                "avg_p_fulfillment": round(r[3] or 0, 4),
            }
            for r in rows
        ]

    async def get_timeseries(self, segment: str | None = None) -> list[dict[str, Any]]:
        seg = segment or "All"
        rows = (
            await self.session.execute(
                select(FactPortfolioKpiMonthly)
                .where(FactPortfolioKpiMonthly.segment == seg)
                .order_by(FactPortfolioKpiMonthly.ref_year_month)
            )
        ).scalars().all()
        if not rows and seg != "All":
            rows = (
                await self.session.execute(
                    select(FactPortfolioKpiMonthly)
                    .where(FactPortfolioKpiMonthly.segment == "All")
                    .order_by(FactPortfolioKpiMonthly.ref_year_month)
                )
            ).scalars().all()
        return [
            {
                "ref_year_month": r.ref_year_month,
                "label": f"{r.ref_year_month[4:6]}/{r.ref_year_month[0:4]}",
                "segment": r.segment,
                "expected_value": round(r.expected_value or 0, 2),
                "actual_collections": round(r.actual_collections or 0, 2),
                "realization_rate": round(r.realization_rate or 0, 4),
                "borrower_count": r.borrower_count,
            }
            for r in rows
        ]

    async def list_settlements_with_installments(self, installments: int) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(FactRecommendedOffer).where(FactRecommendedOffer.optimal_installments == installments)
            )
        ).scalars().all()
        return [
            {
                "customer_code": r.customer_code,
                "settlement_code": r.settlement_code,
                "optimal_rr": r.optimal_rr,
                "expected_value": r.expected_value,
            }
            for r in rows
        ]


class FrontierRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_frontier(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(FactEfficientFrontier))).scalars().all()
        return [
            {
                "strategy_name": r.strategy_name,
                "portfolio_ev": r.portfolio_ev,
                "risk_level": r.risk_level,
                "risk_score": r.risk_score,
                "min_p_fulfill": r.min_p_fulfill,
                "max_rr": r.max_rr,
            }
            for r in rows
        ]

    async def optimize_under_constraints(
        self, min_p_fulfill: float | None = None, max_rr: float | None = None
    ) -> dict[str, Any]:
        from app.services.optimizer import OptimizerError, optimize_portfolio
        from app.services.settings_store import load_guardrail_config

        cfg = load_guardrail_config()
        opt_cfg = cfg.get("optimizer") or {}
        rr_min = float(cfg.get("rr_min", 0.20))
        rr_max = float(cfg.get("rr_max", 0.80))

        baseline_ev = (
            await self.session.execute(select(func.sum(FactRecommendedOffer.expected_value)))
        ).scalar() or 0

        borrower_repo = BorrowerRepository(self.session)
        offers_by_customer = await borrower_repo.get_grid_by_customers()
        try:
            result = optimize_portfolio(
                offers_by_customer,
                rr_min=rr_min,
                rr_max=rr_max,
                max_rr=max_rr,
                min_p_fulfill=min_p_fulfill,
                max_avg_rr=opt_cfg.get("max_avg_rr"),
                max_installment_share=opt_cfg.get("max_installment_share", 0.6),
                high_installment_threshold=int(opt_cfg.get("high_installment_threshold", 3)),
            )
        except OptimizerError as exc:
            raise ValueError(str(exc)) from exc

        constrained_ev = result["portfolio_ev"]
        ev_change_pct = round((constrained_ev - baseline_ev) / baseline_ev * 100, 2) if baseline_ev else 0
        return {
            "baseline_portfolio_ev": round(float(baseline_ev), 2),
            "constrained_portfolio_ev": constrained_ev,
            "ev_change_percent": ev_change_pct,
            "borrowers_affected": result["borrowers_assigned"],
            "avg_rr": result["avg_rr"],
            "solver_status": result["solver_status"],
            "mip_gap": result["mip_gap"],
            "optimizer": result["optimizer"],
            "constraints": result["constraints_applied"],
        }


class MonitoringRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(FactModelMonitoring))).scalars().all()
        return [
            {
                "model_name": r.model_name,
                "metric_name": r.metric_name,
                "metric_value": r.metric_value,
                "baseline_value": r.baseline_value,
                "alert_flag": r.alert_flag,
                "drift": round(r.metric_value - r.baseline_value, 4),
            }
            for r in rows
        ]
