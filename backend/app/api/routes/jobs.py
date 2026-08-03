from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import get_role, require_permission
from app.database import get_db
from app.tools.service import ToolService

router = APIRouter(tags=["jobs"])

_jobs: dict[str, dict[str, Any]] = {}


async def _run_frontier_job(job_id: str, min_p_fulfill: float | None, max_rr: float | None, db_factory) -> None:
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    await asyncio.sleep(2)
    async with db_factory() as db:
        tools = ToolService(db)
        result = await tools.frontier_analysis(min_p_fulfill, max_rr)
        if result.get("error"):
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = result["error"]
        else:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = result.get("data")
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/api/frontier/jobs")
async def create_frontier_job(
    min_p_fulfill: float | None = Query(None),
    max_rr: float | None = Query(None),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "strategy_run")
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "constraints": {"min_p_fulfill": min_p_fulfill, "max_rr": max_rr},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    from app.database import AsyncSessionLocal

    asyncio.create_task(_run_frontier_job(job_id, min_p_fulfill, max_rr, AsyncSessionLocal))
    return _jobs[job_id]


@router.get("/api/frontier/jobs/{job_id}")
async def get_frontier_job(job_id: str, role: str = Depends(get_role)) -> dict[str, Any]:
    require_permission(role, "strategy_read")
    job = _jobs.get(job_id)
    if not job:
        return {"job_id": job_id, "status": "not_found"}
    return job
