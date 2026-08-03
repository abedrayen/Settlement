from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import DimCustomer, FactRecommendedOffer, WorkflowTask
from app.tools.service import ToolService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    tools = ToolService(db)

    portfolio = await tools.portfolio_analytics()
    frontier = await tools.frontier_analysis()
    monitoring = await tools.monitoring()

    top_offers = (
        await db.execute(
            select(FactRecommendedOffer).order_by(FactRecommendedOffer.expected_value.desc()).limit(8)
        )
    ).scalars().all()

    sample_code = top_offers[0].customer_code if top_offers else None
    sample_borrower = await tools.borrower_lookup(customer_code=sample_code) if sample_code else {}

    name_by_code: dict[int, str | None] = {}
    if top_offers:
        codes = [r.customer_code for r in top_offers]
        customers = (
            await db.execute(select(DimCustomer).where(DimCustomer.customer_code.in_(codes)))
        ).scalars().all()
        name_by_code = {c.customer_code: c.legal_name for c in customers}

    workflows = (
        await db.execute(
            select(WorkflowTask).order_by(WorkflowTask.created_at.desc()).limit(10)
        )
    ).scalars().all()

    open_workflows = sum(1 for w in workflows if w.status == "open")

    return {
        "kpis": portfolio.get("data", {}).get("kpis", {}),
        "segments": portfolio.get("data", {}).get("segments", []),
        "frontier": frontier.get("data", {}).get("frontier", []),
        "simulation": frontier.get("data", {}).get("simulation", {}),
        "monitoring": monitoring.get("data", {}).get("metrics", []),
        "alerts": monitoring.get("data", {}).get("alerts", []),
        "sample_borrower": sample_borrower.get("data"),
        "top_recommendations": [
            {
                "customer_code": r.customer_code,
                "legal_name": name_by_code.get(r.customer_code),
                "settlement_code": r.settlement_code,
                "optimal_rr": r.optimal_rr,
                "optimal_installments": r.optimal_installments,
                "expected_value": r.expected_value,
                "p_application": r.p_application,
                "p_acceptance": r.p_acceptance,
                "p_fulfillment": r.p_fulfillment,
                "model_version": r.model_version,
            }
            for r in top_offers
        ],
        "workflows": [
            {
                "task_id": str(w.task_id),
                "task_type": w.task_type,
                "customer_code": w.customer_code,
                "status": w.status,
                "reason": w.reason,
            }
            for w in workflows
        ],
        "open_workflow_count": open_workflows,
        "ref_year_month": "202606",
        "model_version": "v3.2",
    }
