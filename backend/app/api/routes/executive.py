from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import get_role, require_permission
from app.database import get_db
from app.models.entities import AgentRecommendation, WorkflowTask
from app.repositories.borrower import PortfolioRepository
from app.tools.service import ToolService

router = APIRouter(prefix="/api/executive", tags=["executive"])


@router.get("/kpis")
async def executive_kpis(
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "executive_read")
    tools = ToolService(db)
    portfolio = await tools.portfolio_analytics()
    frontier = await tools.frontier_analysis()
    monitoring = await tools.monitoring()

    kpis = portfolio.get("data", {}).get("kpis", {})
    segments = portfolio.get("data", {}).get("segments", [])
    repo = PortfolioRepository(db)
    timeseries = await repo.get_timeseries("All")

    workflows = (await db.execute(select(WorkflowTask))).scalars().all()
    recommendations = (await db.execute(select(AgentRecommendation))).scalars().all()

    hitl_required = sum(1 for r in recommendations if not r.guardrail_passed)
    total_recs = len(recommendations) or 1
    automation_ratio = round(1 - (hitl_required / total_recs), 4)

    open_by_queue: dict[str, int] = {}
    aged: list[dict[str, Any]] = []
    now = datetime.utcnow()
    for w in workflows:
        if w.status in {"open", "pending_approval", "escalated"}:
            q = w.assigned_queue or "unassigned"
            open_by_queue[q] = open_by_queue.get(q, 0) + 1
            age_h = (now - w.created_at).total_seconds() / 3600.0 if w.created_at else 0
            aged.append(
                {
                    "task_id": str(w.task_id),
                    "queue": q,
                    "status": w.status,
                    "age_hours": round(age_h, 1),
                    "reason": w.reason,
                }
            )
    aged.sort(key=lambda x: x["age_hours"], reverse=True)

    guardrail_blocks = sum(1 for w in workflows if w.task_type in {"deceased_escalation", "corporate_collections", "law_protection_review"})
    guardrail_warnings = sum(1 for w in workflows if w.status == "pending_approval")
    guardrail_passed = sum(1 for r in recommendations if r.guardrail_passed)

    # Risk heatmap: segment × PoF bucket
    heatmap: list[dict[str, Any]] = []
    for s in segments:
        pof = float(s.get("avg_p_fulfillment") or 0)
        if pof >= 0.75:
            bucket = "high_pof"
        elif pof >= 0.55:
            bucket = "medium_pof"
        else:
            bucket = "low_pof"
        heatmap.append(
            {
                "segment": s.get("segment"),
                "bucket": bucket,
                "borrower_count": s.get("borrower_count"),
                "total_ev": s.get("total_ev"),
                "avg_p_fulfillment": s.get("avg_p_fulfillment"),
            }
        )

    # Simple forecast: extend last timeseries point by average growth
    forecast: list[dict[str, Any]] = []
    if len(timeseries) >= 2:
        last = timeseries[-1]
        prev = timeseries[-2]
        ev_delta = (last.get("expected_value") or 0) - (prev.get("expected_value") or 0)
        coll_delta = (last.get("actual_collections") or 0) - (prev.get("actual_collections") or 0)
        try:
            ym = last.get("ref_year_month") or last.get("label") or "202606"
            year, month = int(str(ym)[:4]), int(str(ym)[4:6])
        except (TypeError, ValueError):
            year, month = 2026, 6
        for i in range(1, 4):
            month += 1
            if month > 12:
                month = 1
                year += 1
            label = f"{year}{month:02d}"
            forecast.append(
                {
                    "label": label,
                    "forecasted_ev": round((last.get("expected_value") or 0) + ev_delta * i, 2),
                    "forecasted_collections": round((last.get("actual_collections") or 0) + coll_delta * i, 2),
                }
            )

    frontier_points = frontier.get("data", {}).get("frontier", [])
    alerts = monitoring.get("data", {}).get("alerts", [])

    return {
        "recovery_rate": kpis.get("realization_rate"),
        "automation_ratio": automation_ratio,
        "portfolio_exposure": kpis.get("total_outstanding_balance") or 0,
        "total_expected_value": kpis.get("total_expected_value") or 0,
        "total_collections": kpis.get("total_collections") or 0,
        "ev_vs_actual_delta": round(
            (kpis.get("total_expected_value") or 0) - (kpis.get("total_collections") or 0), 2
        ),
        "borrower_count": kpis.get("borrower_count") or 0,
        "risk_segmentation": segments,
        "risk_heatmap": heatmap,
        "workflow_bottlenecks": {
            "open_by_queue": open_by_queue,
            "oldest": aged[:8],
            "open_count": sum(open_by_queue.values()),
        },
        "policy_effectiveness": {
            "passed": guardrail_passed,
            "warnings": guardrail_warnings,
            "blocks": guardrail_blocks,
            "hitl_required": hitl_required,
            "total_recommendations": len(recommendations),
        },
        "forecasted_recoveries": forecast,
        "timeseries": timeseries,
        "frontier": frontier_points,
        "alerts": alerts,
        "as_of": (datetime.utcnow() - timedelta(0)).isoformat() + "Z",
    }
