from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import get_role, require_permission
from app.database import get_db
from app.guardrails.engine import GuardrailEngine
from app.repositories.borrower import BorrowerRepository
from app.tools.service import ToolService

router = APIRouter(prefix="/api/borrowers", tags=["borrowers"])


class WhatIfRequest(BaseModel):
    max_rr: float | None = None
    min_p_fulfill: float | None = None
    fixed_installments: int | None = None


class ScoreRequest(BaseModel):
    recovery_rate: float | None = None
    installments: int | None = None
    rescore_grid: bool = False


class SubmitApprovalRequest(BaseModel):
    reason: str | None = None


@router.get("")
@router.get("/")
async def list_borrowers(
    q: str | None = Query(None),
    segment: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "borrower")
    repo = BorrowerRepository(db)
    return await repo.list_customers(q=q, segment=segment, status=status, limit=limit, offset=offset)


@router.get("/search")
async def search_borrowers(
    q: str,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    require_permission(role, "borrower")
    repo = BorrowerRepository(db)
    return await repo.search(q)


@router.get("/{customer_code}")
async def get_borrower(
    customer_code: int,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "borrower")
    repo = BorrowerRepository(db)
    profile = await repo.get_by_customer_code(customer_code)
    if not profile:
        raise HTTPException(404, "Borrower not found")
    guardrails = GuardrailEngine(db)
    guard = await guardrails.evaluate(customer_code)
    applications = await repo.get_applications(customer_code)
    payments = await repo.get_payments(customer_code)
    activities = await repo.get_activities(customer_code)
    return {
        "customer_code": profile.customer_code,
        "settlement_code": profile.settlement_code,
        "customer": profile.customer,
        "settlement": profile.settlement,
        "recommended_offer": profile.recommended,
        "accounts": profile.accounts,
        "guardrails": guard.__dict__,
        "applications_summary": applications,
        "payments_summary": payments,
        "activities_summary": activities,
    }


@router.get("/{customer_code}/payments")
async def get_payments(
    customer_code: int,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "borrower")
    tools = ToolService(db)
    result = await tools.payment_history(customer_code)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return result.get("data", {})


@router.post("/{customer_code}/submit-approval")
async def submit_approval(
    customer_code: int,
    body: SubmitApprovalRequest | None = None,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "borrower")
    repo = BorrowerRepository(db)
    profile = await repo.get_by_customer_code(customer_code)
    if not profile:
        raise HTTPException(404, "Borrower not found")

    guardrails = GuardrailEngine(db)
    guard = await guardrails.evaluate(customer_code)
    rec = profile.recommended or {}
    legal_name = profile.customer.get("legal_name")
    offer = {
        "customer_code": customer_code,
        "recovery_rate": rec.get("optimal_rr"),
        "installments": rec.get("optimal_installments"),
        "expected_value": rec.get("expected_value"),
        "p_application": rec.get("p_application"),
        "p_acceptance": rec.get("p_acceptance"),
        "p_fulfillment": rec.get("p_fulfillment"),
        "solver_status": rec.get("solver_status"),
        "model_version": rec.get("model_version"),
    }
    decision = guardrails.classify_decision(guard, offer, legal_name=legal_name)
    reason = (body.reason if body and body.reason else None) or decision.get("approval_reason") or "Manual submit for approval"
    queue = decision.get("approver_queue") or "manager_approval"
    payload = {
        **offer,
        "legal_name": legal_name,
        "guardrail_status": guard.status,
        "guardrail_reason": guard.reason,
        "within_limits": decision.get("within_limits"),
        "customer_explanation": decision.get("customer_explanation"),
        "approval_reason": decision.get("approval_reason"),
    }
    task = await guardrails.create_approval_task(
        customer_code=customer_code,
        settlement_code=profile.settlement_code,
        queue=queue,
        reason=str(reason)[:100],
        risk_tier=str(decision.get("risk_tier") or guard.risk_tier or "medium"),
        decision_payload=payload,
    )
    return {
        "task_id": str(task.task_id),
        "status": task.status,
        "assigned_queue": task.assigned_queue,
        "risk_tier": task.risk_tier,
        "reason": task.reason,
        "decision_payload": payload,
    }


@router.get("/{customer_code}/offers")
async def get_offers(
    customer_code: int,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "borrower")
    repo = BorrowerRepository(db)
    grid = await repo.get_offer_grid(customer_code)
    profile = await repo.get_by_customer_code(customer_code)
    if not profile:
        raise HTTPException(404, "Borrower not found")
    return {"grid": grid, "recommended": profile.recommended}


@router.post("/{customer_code}/what-if")
async def what_if(
    customer_code: int,
    body: WhatIfRequest,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "borrower")
    tools = ToolService(db)
    result = await tools.offer_optimization(
        customer_code, body.max_rr, body.min_p_fulfill, body.fixed_installments
    )
    if result.get("blocked"):
        raise HTTPException(422, detail=result)
    return result


@router.get("/{customer_code}/explain")
async def explain(
    customer_code: int,
    model: str = "PoA_v3.1",
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "borrower")
    tools = ToolService(db)
    result = await tools.explainability(customer_code, model)
    return result.get("data", {})


@router.post("/{customer_code}/score")
async def score_borrower(
    customer_code: int,
    body: ScoreRequest | None = None,
    role: str = Depends(get_role),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_permission(role, "borrower")
    tools = ToolService(db)
    req = body or ScoreRequest()
    result = await tools.model_score(
        customer_code,
        recovery_rate=req.recovery_rate,
        installments=req.installments,
        rescore_grid=req.rescore_grid,
    )
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return result.get("data", {})
