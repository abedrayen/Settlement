from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import get_role, require_permission
from app.database import get_db
from app.tools.service import ToolService

router = APIRouter(prefix="/api", tags=["strategy"])


@router.get("/frontier")
async def frontier(
    min_p_fulfill: float | None = Query(None),
    max_rr: float | None = Query(None),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "strategy_read")
    tools = ToolService(db)
    result = await tools.frontier_analysis(min_p_fulfill, max_rr)
    return result.get("data", {})


@router.get("/monitoring")
async def monitoring(role: str = Depends(get_role), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    from app.auth.rbac import ROLE_PERMISSIONS, normalize_role

    r = normalize_role(role)
    perms = ROLE_PERMISSIONS.get(r, set())
    if "portfolio_read" not in perms and "strategy_read" not in perms:
        require_permission(role, "portfolio_read")
    tools = ToolService(db)
    result = await tools.monitoring()
    return result.get("data", {})
