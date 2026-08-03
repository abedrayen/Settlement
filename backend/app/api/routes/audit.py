from __future__ import annotations

import csv
import io
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import get_role, require_permission
from app.database import get_db
from app.models.entities import AgentAuditTrail, AgentConversation, AgentMessage, AgentRecommendation, AgentToolCall
from app.services.settings_store import get_data_freshness, get_model_versions

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditExportQuery(BaseModel):
    format: str = "csv"


@router.get("")
async def list_audit(
    event_type: str | None = Query(None),
    customer_code: int | None = Query(None),
    guardrail_only: bool = Query(False),
    limit: int = Query(100, le=500),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "audit_read")

    rec_query = select(AgentRecommendation).order_by(AgentRecommendation.created_at.desc()).limit(limit)
    if customer_code:
        rec_query = rec_query.where(AgentRecommendation.customer_code == customer_code)
    if guardrail_only:
        rec_query = rec_query.where(AgentRecommendation.guardrail_passed.is_(False))

    recs = (await db.execute(rec_query)).scalars().all()
    recommendations = [
        {
            "type": "recommendation",
            "recommendation_id": str(r.recommendation_id),
            "conversation_id": str(r.conversation_id),
            "customer_code": r.customer_code,
            "settlement_code": r.settlement_code,
            "recommended_rr": r.recommended_rr,
            "recommended_installments": r.recommended_installments,
            "expected_value": r.expected_value,
            "p_application": r.p_application,
            "p_acceptance": r.p_acceptance,
            "p_fulfillment": r.p_fulfillment,
            "model_version": r.model_version,
            "mip_gap": r.mip_gap,
            "guardrail_passed": r.guardrail_passed,
            "data_vintage": "202606",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recs
    ]

    tc_query = select(AgentToolCall).order_by(AgentToolCall.executed_at.desc()).limit(limit)
    if event_type:
        tc_query = tc_query.where(AgentToolCall.tool_name == event_type)
    tool_calls = (await db.execute(tc_query)).scalars().all()
    tools = [
        {
            "type": "tool_call",
            "tool_call_id": str(t.tool_call_id),
            "conversation_id": str(t.conversation_id),
            "tool_name": t.tool_name,
            "input_payload": t.input_payload,
            "output_payload": t.output_payload,
            "duration_ms": t.duration_ms,
            "data_vintage": "202606",
            "executed_at": t.executed_at.isoformat() if t.executed_at else None,
        }
        for t in tool_calls
    ]

    audit_query = select(AgentAuditTrail).order_by(AgentAuditTrail.created_at.desc()).limit(limit)
    if event_type:
        audit_query = audit_query.where(AgentAuditTrail.event_type == event_type)
    audit_rows = (await db.execute(audit_query)).scalars().all()
    events = [
        {
            "type": "audit_event",
            "audit_id": str(a.audit_id),
            "event_type": a.event_type,
            "actor_id": a.actor_id,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "event_payload": a.event_payload,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in audit_rows
    ]

    entries = sorted(
        recommendations + tools + events,
        key=lambda x: x.get("created_at") or x.get("executed_at") or "",
        reverse=True,
    )[:limit]

    return {"entries": entries, "count": len(entries)}


@router.get("/recommendations")
async def audit_recommendations(
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "audit_read")
    rows = (
        await db.execute(select(AgentRecommendation).order_by(AgentRecommendation.created_at.desc()).limit(50))
    ).scalars().all()
    return [
        {
            "recommendation_id": str(r.recommendation_id),
            "conversation_id": str(r.conversation_id),
            "customer_code": r.customer_code,
            "settlement_code": r.settlement_code,
            "recommended_rr": r.recommended_rr,
            "recommended_installments": r.recommended_installments,
            "expected_value": r.expected_value,
            "p_application": r.p_application,
            "p_acceptance": r.p_acceptance,
            "p_fulfillment": r.p_fulfillment,
            "model_version": r.model_version,
            "mip_gap": r.mip_gap,
            "guardrail_passed": r.guardrail_passed,
            "data_vintage": "202606",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/export")
async def export_audit(
    format: str = Query("csv"),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
):
    require_permission(role, "audit_export")
    data = await list_audit(limit=500, role=role, db=db)
    entries = data["entries"]

    if format == "json":
        content = json.dumps(entries, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_export.json"},
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["type", "timestamp", "actor_or_tool", "customer_code", "summary", "guardrail_passed", "model_version"])
    for e in entries:
        ts = e.get("created_at") or e.get("executed_at") or ""
        if e["type"] == "recommendation":
            writer.writerow([
                "recommendation",
                ts,
                "",
                e.get("customer_code"),
                f"RR {e.get('recommended_rr')} / {e.get('recommended_installments')} inst EV {e.get('expected_value')}",
                e.get("guardrail_passed"),
                e.get("model_version"),
            ])
        elif e["type"] == "tool_call":
            writer.writerow(["tool_call", ts, e.get("tool_name"), "", json.dumps(e.get("input_payload"), default=str)[:200], "", ""])
        else:
            writer.writerow(["audit_event", ts, e.get("actor_id"), "", e.get("event_type"), "", ""])

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )


@router.get("/conversations")
async def list_conversations(
    q: str | None = Query(None),
    limit: int = Query(30, le=100),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "chat")
    query = select(AgentConversation).order_by(AgentConversation.started_at.desc()).limit(limit)
    convs = (await db.execute(query)).scalars().all()
    results = []
    for c in convs:
        first_msg = (
            await db.execute(
                select(AgentMessage)
                .where(AgentMessage.conversation_id == c.conversation_id, AgentMessage.role == "user")
                .order_by(AgentMessage.created_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        preview = (first_msg.content[:120] + "…") if first_msg and len(first_msg.content) > 120 else (first_msg.content if first_msg else "")
        if q and q.lower() not in preview.lower():
            continue
        results.append({
            "conversation_id": str(c.conversation_id),
            "role": c.role,
            "domain": c.domain,
            "preview": preview,
            "started_at": c.started_at.isoformat() if c.started_at else None,
        })
    return results


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "chat")
    try:
        cid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(400, "Invalid conversation_id")
    rows = (
        await db.execute(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == cid)
            .order_by(AgentMessage.created_at.asc())
        )
    ).scalars().all()
    return [
        {
            "role": r.role,
            "content": r.content,
            "intent": r.intent,
            "metadata": r.metadata_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
