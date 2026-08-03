from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AgentOrchestrator
from app.auth.rbac import CurrentUser, get_current_user, get_role, normalize_role, require_permission
from app.database import AsyncSessionLocal, get_db
from app.models.entities import WorkflowTask
from app.rag.service import RAGService

router = APIRouter(tags=["agent"])

APPROVER_ROLES = {"manager", "admin"}
APPROVAL_STATUSES = {"approved", "rejected", "escalated"}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class DocumentQuery(BaseModel):
    question: str


class WorkflowUpdate(BaseModel):
    status: str
    resolution_note: str | None = None


@router.post("/api/chat")
async def chat(
    body: ChatRequest,
    role: str = Depends(get_role),
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    require_permission(role, "chat")

    async def event_stream():
        async with AsyncSessionLocal() as db:
            try:
                orchestrator = AgentOrchestrator(db)
                conv_id = UUID(body.conversation_id) if body.conversation_id else None
                async for event in orchestrator.run_stream(
                    body.message, role, conv_id, actor_id=user.email
                ):
                    yield f"data: {json.dumps(event, default=str)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/chat/sync")
async def chat_sync(
    body: ChatRequest,
    role: str = Depends(get_role),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "chat")
    orchestrator = AgentOrchestrator(db)
    conv_id = UUID(body.conversation_id) if body.conversation_id else None
    return await orchestrator.run(body.message, role, conv_id, actor_id=user.email)


@router.post("/api/documents/query")
async def document_query(
    body: DocumentQuery,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "documents_read")
    rag = RAGService(db)
    result = await rag.answer(body.question)
    return result


@router.post("/api/documents/ingest")
async def document_ingest(
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    require_permission(role, "settings_write")
    rag = RAGService(db)
    count = await rag.ingest_documents()
    return {"chunks_ingested": count}


def _workflow_dict(r: WorkflowTask) -> dict[str, Any]:
    payload = r.decision_payload or {}
    legal_name = payload.get("legal_name")
    display = (
        f"{legal_name} ({r.customer_code})"
        if legal_name and r.customer_code
        else (str(r.customer_code) if r.customer_code else None)
    )
    return {
        "task_id": str(r.task_id),
        "task_type": r.task_type,
        "customer_code": r.customer_code,
        "legal_name": legal_name,
        "display_name": display,
        "settlement_code": r.settlement_code,
        "status": r.status,
        "assigned_queue": r.assigned_queue,
        "reason": r.reason,
        "risk_tier": r.risk_tier,
        "priority": r.priority,
        "conversation_id": str(r.conversation_id) if r.conversation_id else None,
        "decision_payload": payload,
        "resolution_note": r.resolution_note,
        "resolved_by": r.resolved_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/api/workflows")
async def list_workflows(
    status: str | None = Query(None),
    queue: str | None = Query(None),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "workflows")
    stmt = select(WorkflowTask).order_by(WorkflowTask.created_at.desc())
    if status:
        stmt = stmt.where(WorkflowTask.status == status)
    if queue:
        stmt = stmt.where(WorkflowTask.assigned_queue == queue)
    rows = (await db.execute(stmt)).scalars().all()
    return [_workflow_dict(r) for r in rows]


@router.get("/api/workflows/kpis")
async def workflow_kpis(
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "workflows")
    rows = (await db.execute(select(WorkflowTask))).scalars().all()
    total = len(rows)
    pending = sum(1 for r in rows if r.status == "pending_approval")
    escalated = sum(1 for r in rows if r.status == "escalated")
    approved = sum(1 for r in rows if r.status == "approved")
    rejected = sum(1 for r in rows if r.status == "rejected")
    decided = approved + rejected
    approval_rate = round(approved / decided, 4) if decided else 0.0

    resolution_hours: list[float] = []
    sla_breaches = 0
    sla_hours = 48.0
    now = datetime.utcnow()
    for r in rows:
        if r.created_at and r.updated_at and r.status in APPROVAL_STATUSES | {"resolved", "acknowledged"}:
            delta = (r.updated_at - r.created_at).total_seconds() / 3600.0
            resolution_hours.append(delta)
        if r.status in {"open", "pending_approval", "escalated"} and r.created_at:
            age_h = (now - r.created_at).total_seconds() / 3600.0
            if age_h > sla_hours:
                sla_breaches += 1

    avg_resolution_hours = round(sum(resolution_hours) / len(resolution_hours), 2) if resolution_hours else 0.0
    return {
        "total": total,
        "pending_approval": pending,
        "escalated": escalated,
        "approved": approved,
        "rejected": rejected,
        "approval_rate": approval_rate,
        "avg_resolution_hours": avg_resolution_hours,
        "sla_breaches": sla_breaches,
        "sla_hours": sla_hours,
    }


@router.patch("/api/workflows/{task_id}")
async def update_workflow(
    task_id: str,
    body: WorkflowUpdate,
    role: str = Depends(get_role),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "workflows")
    task = await db.get(WorkflowTask, UUID(task_id))
    if not task:
        raise HTTPException(404, "Task not found")

    new_status = body.status
    if new_status in APPROVAL_STATUSES and normalize_role(role) not in APPROVER_ROLES:
        raise HTTPException(403, "Only manager or admin can approve/reject/escalate")

    task.status = new_status
    task.updated_at = datetime.utcnow()
    if body.resolution_note is not None:
        task.resolution_note = body.resolution_note
    if new_status in APPROVAL_STATUSES | {"resolved", "acknowledged"}:
        task.resolved_by = user.email
    await db.commit()
    await db.refresh(task)
    return _workflow_dict(task)
