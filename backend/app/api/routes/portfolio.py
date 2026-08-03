from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import get_role, require_permission
from app.database import get_db
from app.repositories.borrower import PortfolioRepository
from app.tools.service import ToolService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/kpis")
async def kpis(role: str = Depends(get_role), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    require_permission(role, "portfolio_read")
    tools = ToolService(db)
    result = await tools.portfolio_analytics()
    kpis = result.get("data", {}).get("kpis", {})
    actual = kpis.get("total_collections", 0)
    ev = kpis.get("total_expected_value", 0)
    kpis["ev_vs_actual_delta"] = round(ev - actual, 2)
    kpis["ev_vs_actual_pct"] = round((ev - actual) / actual * 100, 2) if actual else 0
    if "realization_trend_delta" not in kpis:
        kpis["realization_trend_delta"] = 0.0
    if "total_outstanding_balance" not in kpis:
        kpis["total_outstanding_balance"] = 0
    return kpis


@router.get("/segments")
async def segments(
    segment: str | None = Query(None),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "portfolio_read")
    tools = ToolService(db)
    result = await tools.portfolio_analytics()
    rows = result.get("data", {}).get("segments", [])
    if segment:
        rows = [r for r in rows if r.get("segment", "").lower() == segment.lower()]
    return rows


@router.get("/timeseries")
async def timeseries(
    segment: str | None = Query(None),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "portfolio_read")
    repo = PortfolioRepository(db)
    return await repo.get_timeseries(segment)


@router.get("/export")
async def export_portfolio(
    format: str = Query("csv"),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
):
    require_permission(role, "portfolio_read")
    tools = ToolService(db)
    result = await tools.portfolio_analytics()
    segments = result.get("data", {}).get("segments", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["segment", "borrower_count", "total_ev", "avg_p_fulfillment"])
    for s in segments:
        writer.writerow([s["segment"], s["borrower_count"], s["total_ev"], s["avg_p_fulfillment"]])
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=portfolio_segments.csv"},
    )
