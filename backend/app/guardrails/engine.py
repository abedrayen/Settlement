from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import WorkflowTask
from app.repositories.borrower import BorrowerRepository
from app.services.settings_store import load_guardrail_config


@dataclass
class GuardrailResult:
    status: str  # passed | blocked | warning
    checks: list[str] = field(default_factory=list)
    reason: str | None = None
    workflow_type: str | None = None
    risk_tier: str = "low"
    requires_approval: bool = False
    approver_queue: str | None = None
    within_limits: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rr_bounds() -> tuple[float, float]:
    cfg = load_guardrail_config()
    return cfg.get("rr_min", 0.20), cfg.get("rr_max", 0.80)


def _approval_cfg() -> dict[str, Any]:
    return load_guardrail_config().get("approval") or {}


class GuardrailEngine:
    def __init__(self, session: AsyncSession):
        self.repo = BorrowerRepository(session)
        self.session = session

    async def evaluate(self, customer_code: int, recovery_rate: float | None = None) -> GuardrailResult:
        profile = await self.repo.get_by_customer_code(customer_code)
        if not profile:
            return GuardrailResult(status="blocked", reason="Borrower not found", checks=[], within_limits=False)

        c = profile.customer
        checks: list[str] = []
        approval = _approval_cfg()
        specialist = approval.get("specialist_queues") or {}

        if c.get("flag_deceased") == 1:
            await self._create_workflow(customer_code, profile.settlement_code, "deceased_escalation", "FlagDeceased")
            return GuardrailResult(
                status="blocked",
                reason="FlagDeceased",
                checks=["deceased_check"],
                workflow_type="deceased_escalation",
                risk_tier="high",
                requires_approval=True,
                approver_queue=specialist.get("FlagDeceased", "deceased_escalation"),
                within_limits=False,
            )

        if c.get("flag_legal_entity") == 1:
            await self._create_workflow(
                customer_code, profile.settlement_code, "corporate_collections", "FlagLegalEntity"
            )
            return GuardrailResult(
                status="blocked",
                reason="FlagLegalEntity",
                checks=["legal_entity_check"],
                workflow_type="corporate_collections",
                risk_tier="high",
                requires_approval=True,
                approver_queue=specialist.get("FlagLegalEntity", "corporate_collections"),
                within_limits=False,
            )

        if c.get("flag_under_law_protection") == 1:
            await self._create_workflow(
                customer_code, profile.settlement_code, "law_protection_review", "FlagUnderLawProtection"
            )
            return GuardrailResult(
                status="blocked",
                reason="FlagUnderLawProtection",
                checks=["law_protection_check"],
                workflow_type="law_protection_review",
                risk_tier="high",
                requires_approval=True,
                approver_queue=specialist.get("FlagUnderLawProtection", "law_protection_review"),
                within_limits=False,
            )

        checks.extend(["not_deceased", "not_legal_entity", "not_law_protected"])

        rr = recovery_rate
        if rr is None and profile.recommended:
            rr = profile.recommended.get("optimal_rr")
        rr_min, rr_max = _rr_bounds()
        if rr is not None:
            if rr < rr_min or rr > rr_max:
                return GuardrailResult(
                    status="blocked",
                    reason="RecoveryRateOutOfBounds",
                    checks=checks + ["rr_bounds_failed"],
                    risk_tier="high",
                    requires_approval=True,
                    approver_queue=approval.get("compliance_queue", "compliance_review"),
                    within_limits=False,
                )
            checks.append("rr_bounds")

        if c.get("vulnerability_status") and c.get("vulnerability_status") != "None":
            checks.append("vulnerability_flagged")
            return GuardrailResult(
                status="warning",
                reason="VulnerabilityStatus",
                checks=checks,
                risk_tier="high",
                requires_approval=True,
                approver_queue=approval.get("high_risk_queue", "manager_approval"),
                within_limits=True,
            )

        if c.get("ood_flag"):
            checks.append("out_of_distribution")
            return GuardrailResult(
                status="warning",
                reason="OutOfDistribution",
                checks=checks,
                risk_tier="high",
                requires_approval=True,
                approver_queue=approval.get("high_risk_queue", "manager_approval"),
                within_limits=True,
            )

        return GuardrailResult(status="passed", checks=checks, risk_tier="low", within_limits=True)

    def classify_decision(
        self,
        guard: GuardrailResult,
        offer: dict[str, Any],
        legal_name: str | None = None,
    ) -> dict[str, Any]:
        """Approval tree over a recommended offer."""
        approval = _approval_cfg()
        rr_min, rr_max = _rr_bounds()
        proximity = float(approval.get("rr_bound_proximity", 0.05))
        ev_high = float(approval.get("ev_high_threshold", 5000))

        rr = float(offer.get("recovery_rate") or 0)
        ev = float(offer.get("expected_value") or 0)
        customer_code = offer.get("customer_code")
        display = f"{legal_name} ({customer_code})" if legal_name and customer_code else str(customer_code or "")

        if guard.status == "blocked":
            return {
                "within_limits": False,
                "requires_approval": True,
                "approver_queue": guard.approver_queue,
                "risk_tier": "high",
                "approval_reason": guard.reason,
                "customer_explanation": (
                    f"We cannot proceed with an automated settlement recommendation for {display}. "
                    "The case has been routed for specialist review."
                ),
            }

        risk_tier = guard.risk_tier or "low"
        requires = guard.requires_approval
        queue = guard.approver_queue
        reasons: list[str] = []

        if guard.status == "warning":
            requires = True
            risk_tier = "high"
            queue = queue or approval.get("high_risk_queue", "manager_approval")
            reasons.append(guard.reason or "warning")

        near_bound = (rr - rr_min) <= proximity or (rr_max - rr) <= proximity
        if near_bound:
            risk_tier = "high" if risk_tier == "high" else "medium"
            requires = True
            queue = queue or approval.get("medium_risk_queue", "manager_approval")
            reasons.append("RRNearBounds")

        if ev >= ev_high:
            risk_tier = "high"
            requires = True
            queue = queue or approval.get("high_risk_queue", "manager_approval")
            reasons.append("HighEV")

        customer_explanation = (
            f"For {display}, the recommended settlement is {rr:.0%} recovery over "
            f"{int(offer.get('installments') or 0)} installment(s), with expected value £{ev:,.0f}. "
        )
        if requires:
            customer_explanation += "This recommendation requires manager approval before it can be issued."
        else:
            customer_explanation += "This recommendation is within standard policy limits."

        return {
            "within_limits": guard.within_limits,
            "requires_approval": requires,
            "approver_queue": queue if requires else None,
            "risk_tier": risk_tier,
            "approval_reason": ", ".join(reasons) if reasons else None,
            "customer_explanation": customer_explanation,
        }

    async def create_approval_task(
        self,
        customer_code: int,
        settlement_code: int,
        queue: str,
        reason: str,
        risk_tier: str | None = None,
        decision_payload: dict | None = None,
        conversation_id: UUID | None = None,
    ) -> WorkflowTask:
        return await self.create_workflow_task(
            customer_code=customer_code,
            settlement_code=settlement_code,
            task_type="approval_required",
            reason=reason,
            queue=queue,
            status="pending_approval",
            risk_tier=risk_tier or "medium",
            decision_payload=decision_payload,
            conversation_id=conversation_id,
        )

    async def create_workflow_task(
        self,
        *,
        customer_code: int | None,
        settlement_code: int | None,
        task_type: str,
        reason: str,
        queue: str,
        status: str = "open",
        risk_tier: str | None = None,
        decision_payload: dict | None = None,
        conversation_id: UUID | None = None,
        priority: int = 50,
    ) -> WorkflowTask:
        task = WorkflowTask(
            task_id=uuid4(),
            task_type=task_type,
            customer_code=customer_code,
            settlement_code=settlement_code,
            status=status,
            assigned_queue=queue,
            reason=reason[:100] if reason else None,
            risk_tier=risk_tier,
            priority=priority,
            conversation_id=conversation_id,
            decision_payload=decision_payload,
        )
        self.session.add(task)
        await self.session.commit()
        return task

    async def _create_workflow(
        self, customer_code: int, settlement_code: int, task_type: str, reason: str
    ) -> WorkflowTask:
        return await self.create_workflow_task(
            customer_code=customer_code,
            settlement_code=settlement_code,
            task_type=task_type,
            reason=reason,
            queue=task_type,
            status="open",
            risk_tier="high",
            priority=10,
        )
