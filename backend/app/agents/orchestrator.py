from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.guardrails.engine import GuardrailEngine
from app.models.entities import (
    AgentAuditTrail,
    AgentConversation,
    AgentMessage,
    AgentRecommendation,
    AgentToolCall,
)
from app.rag.service import RAGService
from app.tools.service import ToolService

SYSTEM_PROMPT = """You are a friendly, expert Decision Intelligence assistant for debt settlement portfolios.

Personality:
- Conversational and warm — like a knowledgeable colleague, not a report generator
- Acknowledge the user's question naturally before presenting findings
- Use first person ("I looked up...", "Based on the portfolio data...")
- Keep responses focused: 2–4 short paragraphs unless the user asks for detail

Rules:
- You orchestrate tools — you NEVER calculate EV or probabilities yourself
- Always cite exact numbers from the tool results provided — do not invent or round them
- Always refer to borrowers as "Legal Name (customer_code)", never code alone
- Use probabilistic language (e.g. "Predicted acceptance probability: 64%")
- Never present predictions as certainties
- For follow-up questions, use the conversation history for context
- When recommending settlements, include model version, EV, probabilities, solver status, and guardrail status
- If guardrails block a recommendation, explain why empathetically and mention workflow escalation
- If no tool data is available, ask a clarifying question conversationally"""

MISSING_IDENTITY = (
    "Which customer should I look up? Please share their **name** and **customer code** "
    "(for example: Jane Smith 243445)."
)


def _extract_customer_code(text: str) -> int | None:
    patterns = [
        r"borrower\s+(\d{5,6})",
        r"customer\s+(\d{5,6})",
        r"customer_code[:\s]+(\d{5,6})",
        r"\((\d{5,6})\)",
        r"\b(2434\d{2})\b",
        r"\b(243\d{3})\b",
        r"\b(\d{6})\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return int(m.group(1))
    return None


def _extract_name_hint(text: str) -> str | None:
    quoted = re.search(r'["“]([^"”]+)["”]', text)
    if quoted:
        return quoted.group(1).strip()

    patterns = [
        r"(?:borrower|customer|for|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        r"(?:borrower|customer|for|about)\s+([A-Za-z][A-Za-z\-']+(?:\s+[A-Za-z][A-Za-z\-']+){1,3})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            name = m.group(1).strip()
            # Strip trailing code if captured
            name = re.sub(r"\s+\d{5,6}$", "", name).strip()
            stop = {"what", "why", "how", "show", "recommend", "settlement", "payment", "history", "rescore", "score"}
            if name.lower() not in stop and len(name) >= 3:
                return name

    # Fallback: strip codes and common verbs, keep Capitalized tokens
    cleaned = re.sub(r"\b\d{5,6}\b", " ", text)
    tokens = re.findall(r"\b[A-Z][a-zA-Z\-']+\b", cleaned)
    skip = {
        "I", "What", "Why", "How", "Show", "Recommend", "Settlement", "Payment", "History",
        "Rescore", "Score", "Please", "Can", "Could", "Would", "The", "For", "About",
        "Borrower", "Customer", "Offer", "Portfolio", "Model", "Policy", "Human",
    }
    kept = [t for t in tokens if t not in skip]
    if len(kept) >= 2:
        return " ".join(kept[:3])
    return None


def _borrower_from_history(history: list[dict]) -> dict[str, Any] | None:
    for msg in reversed(history):
        meta = msg.get("metadata") or {}
        for key in ("borrower", "recommendation"):
            blob = meta.get(key) or {}
            if blob.get("customer_code"):
                return {
                    "customer_code": blob["customer_code"],
                    "legal_name": blob.get("legal_name"),
                    "display_name": blob.get("display_name")
                    or (
                        f"{blob.get('legal_name')} ({blob['customer_code']})"
                        if blob.get("legal_name")
                        else str(blob["customer_code"])
                    ),
                }
        for tc in meta.get("tool_calls") or []:
            out = tc.get("output") or {}
            if isinstance(out, dict) and out.get("customer_code"):
                legal = out.get("legal_name")
                code = out["customer_code"]
                return {
                    "customer_code": code,
                    "legal_name": legal,
                    "display_name": out.get("display_name") or (f"{legal} ({code})" if legal else str(code)),
                }
            inp = tc.get("input") or {}
            if inp.get("customer_code"):
                return {
                    "customer_code": inp["customer_code"],
                    "legal_name": inp.get("legal_name"),
                    "display_name": inp.get("display_name") or str(inp["customer_code"]),
                }
        if msg["role"] == "user":
            code = _extract_customer_code(msg["content"])
            if code:
                return {"customer_code": code, "legal_name": None, "display_name": str(code)}
    return None


def _display(borrower: dict[str, Any] | None, customer_code: int | None = None, legal_name: str | None = None) -> str:
    if borrower:
        return borrower.get("display_name") or (
            f"{borrower.get('legal_name')} ({borrower.get('customer_code')})"
            if borrower.get("legal_name")
            else str(borrower.get("customer_code"))
        )
    if legal_name and customer_code:
        return f"{legal_name} ({customer_code})"
    return str(customer_code or "")


def _classify_intent(message: str, history: list[dict]) -> str:
    lower = message.lower()
    if any(w in lower for w in ["hello", "hi ", "hey", "thanks", "thank you", "good morning", "good afternoon"]) and not any(
        w in lower for w in ["borrower", "settlement", "portfolio", "payment", "offer"]
    ):
        return "greeting"
    if any(w in lower for w in ["speak to", "talk to", "human", "representative", "agent please", "handoff", "escalate to human"]):
        return "human_handoff"
    if any(w in lower for w in ["exception", "extension", "grace period", "policy exception", "special approval"]):
        return "policy_exception"
    if any(w in lower for w in ["rescore", "re-score", "model score", "score borrower", "run poapp", "run poa", "run pof"]):
        return "model_score"
    if any(w in lower for w in ["payment history", "paid so far", "what have i paid", "payments for", "instalments covered"]):
        return "payment_history"
    if any(w in lower for w in ["balance", "outstanding", "debt inquiry", "what do they owe", "obligations"]):
        return "debt_inquiry"
    if any(w in lower for w in ["restructure", "restructuring", "monthly capacity", "how many installments can"]):
        return "restructuring"
    if any(w in lower for w in ["renegotiate", "re-negotiate", "more installments", "reduce the installment", "change my plan"]):
        return "renegotiation"
    if any(w in lower for w in ["policy", "document", "regulation", "max recovery", "deceased policy", "vulnerability", "corporate collection"]):
        return "document"
    if any(w in lower for w in ["frontier", "efficient", "what if", "what-if", "cap", "constraint", "rr capped", "scenario", "optimize portfolio"]):
        return "strategy"
    if any(w in lower for w in ["portfolio", "segment", "kpi", "realization", "drift", "monitoring", "psi", "underperform", "model health"]):
        return "portfolio"
    if any(w in lower for w in ["why", "explain", "shap", "driver", "not approved"]):
        return "decision_explanation"
    if any(w in lower for w in ["recommend", "guidance", "what can i do", "best offer", "optimal offer"]):
        return "recommendation"
    if any(w in lower for w in ["offer", "settlement", "borrower", "customer", "installment"]):
        return "recommendation"
    if history and any(w in lower for w in ["why", "explain", "more", "detail", "that", "same", "also", "what about", "how about"]):
        return "recommendation"
    return "recommendation"


def _parse_frontier_constraints(message: str) -> tuple[float | None, float | None]:
    lower = message.lower()
    min_pf = None
    max_rr = None
    pf_match = re.search(r"(?:p[_\s]?fulfill(?:ment)?|fulfillment)\s*(?:>=?|at least|above|min(?:imum)?)\s*(\d+(?:\.\d+)?)\s*%?", lower)
    if pf_match:
        val = float(pf_match.group(1))
        min_pf = val / 100 if val > 1 else val
    elif "70" in message and any(w in lower for w in ["fulfill", "pf", "p_f"]):
        min_pf = 0.70
    rr_match = re.search(r"(?:rr|recovery\s*rate)\s*(?:<=?|capped|cap|max(?:imum)?|below)\s*(\d+(?:\.\d+)?)\s*%?", lower)
    if rr_match:
        val = float(rr_match.group(1))
        max_rr = val / 100 if val > 1 else val
    elif "50" in message and "rr" in lower:
        max_rr = 0.50
    return min_pf, max_rr


def _parse_offer_constraints(message: str) -> dict[str, Any]:
    min_pf, max_rr = _parse_frontier_constraints(message)
    fixed = None
    m = re.search(r"(\d+)\s*installments?", message, re.I)
    if m:
        fixed = int(m.group(1))
    return {"max_rr": max_rr, "min_p_fulfill": min_pf, "fixed_installments": fixed}


def _wants_explain(message: str) -> bool:
    lower = message.lower()
    return any(w in lower for w in ["why", "explain", "shap", "driver", "factor", "reason"])


def _wants_offer_grid(message: str) -> bool:
    lower = message.lower()
    return any(w in lower for w in ["why", "compare", "grid", " vs ", "versus", "over", "instead of", "alternative", "60%", "40%"])


def _wants_installment_compare(message: str) -> tuple[int, int, int] | None:
    lower = message.lower()
    if not any(w in lower for w in ["installment", "instalment", "payment plan"]):
        return None
    if not any(w in lower for w in ["top", "compare", "change", "switch", "reduce", "increase", "ev"]):
        return None
    from_inst, to_inst = 2, 1
    m = re.search(r"from\s+(\d+)\s+to\s+(\d+)", lower)
    if m:
        from_inst, to_inst = int(m.group(1)), int(m.group(2))
    limit = 5
    lm = re.search(r"top\s+(\d+)", lower)
    if lm:
        limit = int(lm.group(1))
    return from_inst, to_inst, limit


def _wants_portfolio_optimize(message: str) -> bool:
    lower = message.lower()
    return any(w in lower for w in ["optimize portfolio", "portfolio milp", "whole portfolio", "all borrowers"])


class AgentOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tools = ToolService(session)
        self.rag = RAGService(session)
        self.guardrails = GuardrailEngine(session)
        self.client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

    async def run(
        self,
        message: str,
        role: str = "analyst",
        conversation_id: UUID | None = None,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] | None = None
        async for event in self.run_stream(message, role, conversation_id, actor_id=actor_id):
            if event.get("type") == "done":
                result = event
        return result or {}

    async def _resolve_borrower(
        self, message: str, history: list[dict]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Return (borrower_dict, clarification_message)."""
        code = _extract_customer_code(message)
        name_hint = _extract_name_hint(message)

        if code and name_hint:
            hits = await self.tools.borrower_repo.search(name_hint)
            by_code = await self.tools.borrower_repo.get_by_customer_code(code)
            if not by_code:
                return None, f"I couldn't find customer code **{code}**. Please check the name and code."
            legal = by_code.customer.get("legal_name")
            if hits and not any(h["customer_code"] == code for h in hits):
                options = ", ".join(f"{h['legal_name']} ({h['customer_code']})" for h in hits[:5])
                return None, (
                    f"The name **{name_hint}** doesn't match code **{code}** "
                    f"({legal} ({code})). Did you mean one of: {options}?"
                )
            return {
                "customer_code": code,
                "legal_name": legal,
                "display_name": f"{legal} ({code})" if legal else str(code),
            }, None

        if code:
            profile = await self.tools.borrower_repo.get_by_customer_code(code)
            if not profile:
                return None, f"I couldn't find customer code **{code}**. Please share the customer name and code."
            legal = profile.customer.get("legal_name")
            return {
                "customer_code": code,
                "legal_name": legal,
                "display_name": f"{legal} ({code})" if legal else str(code),
            }, None

        if name_hint:
            hits = await self.tools.borrower_repo.search(name_hint)
            if not hits:
                return None, f"I couldn't find a customer named **{name_hint}**. Please share the **name** and **customer code**."
            if len(hits) > 1:
                options = "\n".join(f"- {h['legal_name']} ({h['customer_code']})" for h in hits[:8])
                return None, f"I found multiple matches for **{name_hint}**. Which one did you mean?\n{options}"
            h = hits[0]
            return {
                "customer_code": h["customer_code"],
                "legal_name": h["legal_name"],
                "display_name": f"{h['legal_name']} ({h['customer_code']})",
            }, None

        prior = _borrower_from_history(history)
        if prior and prior.get("customer_code"):
            if not prior.get("legal_name"):
                profile = await self.tools.borrower_repo.get_by_customer_code(prior["customer_code"])
                if profile:
                    legal = profile.customer.get("legal_name")
                    prior["legal_name"] = legal
                    prior["display_name"] = f"{legal} ({prior['customer_code']})" if legal else str(prior["customer_code"])
            return prior, None

        return None, MISSING_IDENTITY

    async def run_stream(
        self,
        message: str,
        role: str = "analyst",
        conversation_id: UUID | None = None,
        actor_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        conv_id = conversation_id or uuid4()
        history = await self._load_history(conv_id)
        actor = actor_id or role

        existing = await self.session.get(AgentConversation, conv_id)
        if not existing:
            intent_guess = _classify_intent(message, history)
            conv = AgentConversation(conversation_id=conv_id, user_id=actor, role=role, domain=intent_guess)
            self.session.add(conv)
            await self.session.flush()

        await self._save_message(conv_id, "user", message)
        intent = _classify_intent(message, history)

        yield {"type": "status", "message": "Understanding your question…"}

        tool_calls: list[dict] = []
        recommendation = None
        guardrail_result = None
        workflow = None
        draft = ""
        borrower_meta: dict[str, Any] | None = None

        if intent == "greeting":
            draft = await self._conversational_reply(message, history, role, None, intent)
            if not draft:
                draft = self._fallback_reply(intent)

        elif intent == "document":
            yield {"type": "tool_start", "tool": "document_rag"}
            rag_result = await self.rag.answer(message)
            tool_calls.append({"tool": "document_rag", "input": {"question": message}, "output": rag_result, "duration_ms": 0})
            yield {"type": "tool_done", "tool": "document_rag", "output": rag_result}
            draft = await self._conversational_reply(message, history, role, {"document_rag": rag_result}, intent)
            if not draft:
                draft = self._fallback_document_answer(rag_result)

        elif intent == "portfolio":
            if any(w in message.lower() for w in ["monitor", "drift", "psi", "model health"]):
                yield {"type": "tool_start", "tool": "monitoring"}
                result = await self.tools.monitoring()
                tool_calls.append({"tool": "monitoring", "input": {}, "output": result.get("data"), "duration_ms": result.get("duration_ms", 0)})
                yield {"type": "tool_done", "tool": "monitoring", "output": result.get("data")}
                draft = self._format_monitoring(result.get("data", {}))
            else:
                yield {"type": "tool_start", "tool": "portfolio_analytics"}
                result = await self.tools.portfolio_analytics()
                tool_calls.append({"tool": "portfolio_analytics", "input": {}, "output": result.get("data"), "duration_ms": result.get("duration_ms", 0)})
                yield {"type": "tool_done", "tool": "portfolio_analytics", "output": result.get("data")}
                draft = self._format_portfolio(result.get("data", {}))
            polished = await self._conversational_reply(message, history, role, {"tool_data": draft}, intent)
            if polished:
                draft = polished

        elif intent == "strategy":
            min_pf, max_rr = _parse_frontier_constraints(message)
            if _wants_portfolio_optimize(message):
                yield {"type": "tool_start", "tool": "offer_optimization"}
                result = await self.tools.offer_optimization(mode="portfolio", max_rr=max_rr, min_p_fulfill=min_pf)
                tool_calls.append({"tool": "offer_optimization", "input": {"mode": "portfolio", "max_rr": max_rr, "min_p_fulfill": min_pf}, "output": result.get("data") or result, "duration_ms": result.get("duration_ms", 0)})
                yield {"type": "tool_done", "tool": "offer_optimization", "output": result.get("data") or result}
                if result.get("error"):
                    draft = f"Portfolio optimisation failed: {result['error']}"
                else:
                    data = result.get("data", {})
                    draft = (
                        f"Portfolio MILP assigned offers to **{data.get('borrowers_assigned')}** borrowers.\n"
                        f"Portfolio EV: £{data.get('portfolio_ev', 0):,.0f} | Avg RR: {float(data.get('avg_rr') or 0)*100:.1f}%\n"
                        f"Solver: {data.get('solver_status')} (MIP gap {float(data.get('mip_gap') or 0)*100:.2f}%)"
                    )
            else:
                yield {"type": "tool_start", "tool": "frontier_analysis"}
                result = await self.tools.frontier_analysis(min_pf, max_rr)
                tool_calls.append({"tool": "frontier_analysis", "input": {"min_p_fulfill": min_pf, "max_rr": max_rr}, "output": result.get("data") or result, "duration_ms": result.get("duration_ms", 0)})
                yield {"type": "tool_done", "tool": "frontier_analysis", "output": result.get("data") or result}
                if result.get("error"):
                    draft = f"Frontier simulation failed: {result['error']}"
                else:
                    draft = self._format_frontier(result.get("data", {}))
            polished = await self._conversational_reply(message, history, role, {"tool_data": draft}, intent)
            if polished:
                draft = polished

        elif intent == "human_handoff":
            borrower, clarify = await self._resolve_borrower(message, history)
            reason = "User requested human handoff"
            yield {"type": "tool_start", "tool": "human_handoff"}
            result = await self.tools.create_handoff(
                customer_code=borrower["customer_code"] if borrower else None,
                settlement_code=None,
                reason=reason,
                conversation_id=conv_id,
                legal_name=borrower.get("legal_name") if borrower else None,
            )
            tool_calls.append({"tool": "human_handoff", "input": {"reason": reason}, "output": result.get("data"), "duration_ms": result.get("duration_ms", 0)})
            yield {"type": "tool_done", "tool": "human_handoff", "output": result.get("data")}
            data = result.get("data", {})
            who = data.get("display_name") or "this conversation"
            draft = (
                f"I've created a human handoff task for **{who}** "
                f"(queue: {data.get('assigned_queue')}, status: {data.get('status')}). "
                "A specialist can pick it up in Workflows."
            )
            workflow = {"type": "human_handoff", "status": data.get("status"), "reason": reason, "task_id": data.get("task_id")}
            if clarify and not borrower:
                draft = clarify + "\n\n" + draft
            borrower_meta = borrower

        elif intent in {
            "debt_inquiry",
            "payment_history",
            "restructuring",
            "recommendation",
            "decision_explanation",
            "renegotiation",
            "policy_exception",
            "model_score",
            "settlement",
        }:
            event_queue: list[dict] = []

            async def capture(event: dict) -> None:
                event_queue.append(event)

            # Run with event capture — flush after for SSE (tools already executed)
            draft, tool_calls, recommendation, guardrail_result, workflow, borrower_meta = await self._run_borrower_intent(
                intent, message, history, tool_calls, conv_id, on_event=capture
            )
            for ev in event_queue:
                yield ev
            for tc in tool_calls:
                # Ensure tool_done was emitted
                if not any(e.get("type") == "tool_done" and e.get("tool") == tc["tool"] for e in event_queue):
                    yield {"type": "tool_done", "tool": tc["tool"], "output": tc.get("output")}

            polished = await self._conversational_reply(
                message,
                history,
                role,
                {"tool_data": draft, "recommendation": recommendation, "guardrails": guardrail_result, "borrower": borrower_meta},
                intent,
            )
            if polished:
                draft = polished
        else:
            draft = self._fallback_reply(intent)

        if not draft:
            draft = self._fallback_reply(intent)

        yield {"type": "answer", "content": draft}

        for tc in tool_calls:
            self.session.add(
                AgentToolCall(
                    tool_call_id=uuid4(),
                    conversation_id=conv_id,
                    tool_name=tc["tool"],
                    input_payload=tc.get("input"),
                    output_payload=tc.get("output"),
                    duration_ms=tc.get("duration_ms"),
                )
            )

        if recommendation:
            self.session.add(
                AgentRecommendation(
                    recommendation_id=uuid4(),
                    conversation_id=conv_id,
                    customer_code=recommendation["customer_code"],
                    settlement_code=recommendation["settlement_code"],
                    recommended_rr=recommendation["recommended_rr"],
                    recommended_installments=recommendation["recommended_installments"],
                    expected_value=recommendation["expected_value"],
                    p_application=recommendation["p_application"],
                    p_acceptance=recommendation["p_acceptance"],
                    p_fulfillment=recommendation["p_fulfillment"],
                    model_version=recommendation["model_version"],
                    mip_gap=recommendation["mip_gap"],
                    guardrail_passed=recommendation.get("guardrail_passed", True),
                )
            )

        self.session.add(
            AgentAuditTrail(
                audit_id=uuid4(),
                event_type="chat_response",
                actor_id=actor,
                entity_type="conversation",
                entity_id=str(conv_id),
                event_payload={"message": message, "intent": intent, "borrower": borrower_meta},
            )
        )

        meta = {
            "intent": intent,
            "tool_calls": tool_calls,
            "recommendation": recommendation,
            "guardrails": guardrail_result,
            "workflow": workflow,
            "borrower": borrower_meta,
        }
        await self._save_message(conv_id, "assistant", draft, intent, meta)
        await self.session.commit()

        yield {
            "type": "done",
            "conversation_id": str(conv_id),
            "answer": draft,
            "tool_calls": tool_calls,
            "recommendation": recommendation,
            "guardrails": guardrail_result,
            "workflow": workflow,
            "intent": intent,
            "borrower": borrower_meta,
        }

    async def _run_borrower_intent(
        self,
        intent: str,
        message: str,
        history: list[dict],
        tool_calls: list,
        conv_id: UUID,
        on_event: Any = None,
    ) -> tuple[str, list, dict | None, dict | None, dict | None, dict | None]:
        async def emit(event: dict) -> None:
            if on_event:
                await on_event(event)

        inst_params = _wants_installment_compare(message)
        if inst_params:
            from_inst, to_inst, limit = inst_params
            await emit({"type": "tool_start", "tool": "installment_comparison"})
            result = await self.tools.installment_comparison(from_inst, to_inst, limit)
            tool_calls.append({
                "tool": "installment_comparison",
                "input": {"from": from_inst, "to": to_inst, "limit": limit},
                "output": result.get("data"),
                "duration_ms": result.get("duration_ms", 0),
            })
            lines = [f"Top {limit} borrowers where changing from {from_inst} to {to_inst} installment(s) increases EV:\n"]
            for i, row in enumerate(result.get("data", []), 1):
                lines.append(
                    f"{i}. Customer {row['customer_code']}: EV £{row['ev_from']:,.0f} → £{row['ev_to']:,.0f} (+£{row['ev_delta']:,.0f})"
                )
            return "\n".join(lines), tool_calls, None, None, None, None

        borrower, clarify = await self._resolve_borrower(message, history)
        if not borrower:
            return clarify or MISSING_IDENTITY, tool_calls, None, None, None, None

        customer_code = int(borrower["customer_code"])
        display = _display(borrower)

        if intent == "policy_exception":
            await emit({"type": "tool_start", "tool": "document_rag"})
            rag_result = await self.rag.answer(message)
            tool_calls.append({"tool": "document_rag", "input": {"question": message}, "output": rag_result, "duration_ms": 0})
            exc = await self.tools.create_exception_request(customer_code, message[:200], conversation_id=conv_id)
            tool_calls.append({"tool": "exception_request", "input": {"customer_code": customer_code}, "output": exc.get("data"), "duration_ms": exc.get("duration_ms", 0)})
            workflow = {"type": "exception_request", "status": exc.get("data", {}).get("status"), "reason": "Policy exception"}
            policy_snip = self._fallback_document_answer(rag_result)
            draft = (
                f"I've logged a policy exception request for **{display}** "
                f"(status: {exc.get('data', {}).get('status')}).\n\n{policy_snip}"
            )
            return draft, tool_calls, None, None, workflow, borrower

        if intent == "payment_history":
            result = await self.tools.payment_history(customer_code)
            tool_calls.append({"tool": "payment_history", "input": {"customer_code": customer_code, "legal_name": borrower.get("legal_name")}, "output": result.get("data"), "duration_ms": result.get("duration_ms", 0)})
            data = result.get("data") or {}
            lines = [
                f"Payment history for **{display}**:",
                f"- Payments recorded: {data.get('count_6m', len(data.get('payments') or []))}",
                f"- Total paid: £{float(data.get('total') or data.get('total_6m') or 0):,.2f}",
            ]
            latest = data.get("latest_date")
            if latest:
                lines.append(f"- Latest payment: {latest}")
            for p in (data.get("payments") or [])[:5]:
                lines.append(
                    f"  · {p.get('payment_date')}: £{float(p.get('payment_amount') or 0):,.2f} ({p.get('payment_type')})"
                )
            return "\n".join(lines), tool_calls, None, None, None, borrower

        if intent == "debt_inquiry":
            lookup = await self.tools.borrower_lookup(customer_code=customer_code)
            tool_calls.append({"tool": "borrower_lookup", "input": {"customer_code": customer_code}, "output": lookup.get("data"), "duration_ms": lookup.get("duration_ms", 0)})
            data = lookup.get("data") or {}
            settlement = data.get("settlement") or {}
            accounts = data.get("accounts") or []
            lines = [
                f"Debt summary for **{display}**:",
                f"- Status: {settlement.get('settlement_status')}",
                f"- Connected balance: £{float(settlement.get('total_balance_connected_loans') or 0):,.2f}",
                f"- Settlement remaining: £{float(settlement.get('settlement_remaining_amount') or 0):,.2f}",
                f"- Accounts: {len(accounts)}",
            ]
            return "\n".join(lines), tool_calls, None, None, None, borrower

        if intent == "model_score":
            result = await self.tools.model_score(customer_code, rescore_grid="grid" in message.lower() or "all" in message.lower())
            tool_calls.append({"tool": "model_score", "input": {"customer_code": customer_code}, "output": result.get("data"), "duration_ms": result.get("duration_ms", 0)})
            if result.get("error"):
                return result["error"], tool_calls, None, None, None, borrower
            data = result.get("data") or {}
            if data.get("best"):
                best = data["best"]
                draft = (
                    f"Rescored offer grid for **{display}** (simulated ModelScorer).\n"
                    f"Best EV offer: RR {float(best['recovery_rate'])*100:.0f}% / {int(best['installments'])} installments — "
                    f"EV £{float(best['expected_value']):,.0f} "
                    f"(PoAPP {float(best['p_application'])*100:.0f}% · PoA {float(best['p_acceptance'])*100:.0f}% · PoF {float(best['p_fulfillment'])*100:.0f}%)"
                )
            else:
                offer = data.get("offer") or {}
                draft = (
                    f"On-demand scores for **{display}**:\n"
                    f"PoAPP {float(offer.get('p_application') or 0)*100:.0f}% · "
                    f"PoA {float(offer.get('p_acceptance') or 0)*100:.0f}% · "
                    f"PoF {float(offer.get('p_fulfillment') or 0)*100:.0f}% · "
                    f"EV £{float(offer.get('expected_value') or 0):,.0f}"
                )
            return draft, tool_calls, None, None, None, borrower

        if intent == "decision_explanation" or _wants_explain(message):
            lookup = await self.tools.borrower_lookup(customer_code=customer_code)
            tool_calls.append({"tool": "borrower_lookup", "input": {"customer_code": customer_code}, "output": lookup.get("data"), "duration_ms": lookup.get("duration_ms", 0)})
            explain = await self.tools.explainability(customer_code)
            tool_calls.append({"tool": "explainability", "input": {"customer_code": customer_code}, "output": explain.get("data"), "duration_ms": explain.get("duration_ms", 0)})
            return self._format_explain(display, explain.get("data", {})), tool_calls, None, None, None, borrower

        # restructuring / renegotiation / recommendation — MILP offer path
        constraints = _parse_offer_constraints(message)
        if intent in {"restructuring", "renegotiation"}:
            # Soft missing-data prompts for optional slots (still run optimize if identity known)
            hints = []
            if constraints["fixed_installments"] is None and "installment" not in message.lower():
                hints.append("desired number of installments")
            if "afford" not in message.lower() and "capacity" not in message.lower() and "month" not in message.lower():
                hints.append("monthly payment capacity")
        else:
            hints = []

        lookup = await self.tools.borrower_lookup(customer_code=customer_code)
        tool_calls.append({"tool": "borrower_lookup", "input": {"customer_code": customer_code, "legal_name": borrower.get("legal_name")}, "output": lookup.get("data"), "duration_ms": lookup.get("duration_ms", 0)})

        if _wants_offer_grid(message):
            grid_result = await self.tools.offer_grid(customer_code)
            tool_calls.append({"tool": "offer_grid", "input": {"customer_code": customer_code}, "output": grid_result.get("data"), "duration_ms": grid_result.get("duration_ms", 0)})

        opt_task = asyncio.create_task(
            self.tools.offer_optimization(
                customer_code,
                max_rr=constraints["max_rr"],
                min_p_fulfill=constraints["min_p_fulfill"],
                fixed_installments=constraints["fixed_installments"],
            )
        )
        explain_task = asyncio.create_task(self.tools.explainability(customer_code))
        opt, explain = await asyncio.gather(opt_task, explain_task)
        tool_calls.append({"tool": "offer_optimization", "input": {"customer_code": customer_code, **constraints}, "output": opt, "duration_ms": opt.get("duration_ms", 0)})
        tool_calls.append({"tool": "explainability", "input": {"customer_code": customer_code}, "output": explain.get("data"), "duration_ms": explain.get("duration_ms", 0)})

        if opt.get("blocked"):
            gr = opt.get("guardrails", {})
            workflow = {"type": gr.get("workflow_type"), "status": "open", "reason": gr.get("reason")}
            answer = (
                f"I can't issue a settlement recommendation for **{display}** — "
                f"guardrail **{gr.get('reason')}**. The case has been escalated."
            )
            return answer, tool_calls, None, gr, workflow, borrower

        if opt.get("error"):
            return f"Optimisation failed for **{display}**: {opt['error']}", tool_calls, None, None, None, borrower

        offer = opt.get("data", {})
        guardrail_result = opt.get("guardrails", {})
        profile = lookup.get("data", {})
        settlement_code = profile.get("settlement_code", 0)
        rr_pct = int(float(offer.get("recovery_rate", 0)) * 100)
        mip_gap = float(offer.get("mip_gap", 0.0))

        recommendation = {
            "customer_code": customer_code,
            "legal_name": borrower.get("legal_name"),
            "display_name": display,
            "settlement_code": settlement_code,
            "recommended_rr": offer.get("recovery_rate"),
            "recommended_installments": offer.get("installments"),
            "expected_value": offer.get("expected_value"),
            "p_application": offer.get("p_application"),
            "p_acceptance": offer.get("p_acceptance"),
            "p_fulfillment": offer.get("p_fulfillment"),
            "model_version": offer.get("model_version", "v3.2"),
            "mip_gap": mip_gap,
            "solver_status": offer.get("solver_status"),
            "optimizer": offer.get("optimizer"),
            "risk_tier": offer.get("risk_tier"),
            "requires_approval": offer.get("requires_approval"),
            "approver_queue": offer.get("approver_queue"),
            "within_limits": offer.get("within_limits"),
            "customer_explanation": offer.get("customer_explanation"),
            "alternatives": offer.get("alternatives"),
            "settlement_amount": float(profile.get("settlement", {}).get("total_balance_connected_loans") or 0)
            * float(offer.get("recovery_rate") or 0),
            "guardrail_passed": guardrail_result.get("status") in {"passed", "warning"},
            "ref_year_month": "202606",
        }

        workflow = None
        if offer.get("requires_approval"):
            workflow = {
                "type": "approval_required",
                "status": "pending_approval",
                "reason": offer.get("approval_reason"),
                "queue": offer.get("approver_queue"),
                "risk_tier": offer.get("risk_tier"),
            }

        answer = (
            f"For **{display}**, I recommend **{rr_pct}% Recovery Rate** "
            f"over **{offer.get('installments')} installments**.\n\n"
            f"**Expected Value:** £{float(offer.get('expected_value') or 0):,.0f}\n"
            f"**P(Application):** {float(offer.get('p_application') or 0)*100:.0f}% | "
            f"**P(Acceptance):** {float(offer.get('p_acceptance') or 0)*100:.0f}% | "
            f"**P(Fulfillment):** {float(offer.get('p_fulfillment') or 0)*100:.0f}%\n\n"
            f"Solver: {offer.get('solver_status', 'Optimal')} ({offer.get('optimizer', 'pulp_cbc')}) | "
            f"MIP Gap: {mip_gap*100:.2f}% | Risk: {offer.get('risk_tier', 'low')}"
        )
        if offer.get("requires_approval"):
            answer += f"\n\n⚠ Requires approval ({offer.get('approver_queue')}): {offer.get('approval_reason')}"
        elif guardrail_result.get("status") == "warning":
            answer += f"\n\n⚠ Note: {guardrail_result.get('reason')} — please review before contacting the borrower."
        if offer.get("customer_explanation"):
            answer += f"\n\n{offer['customer_explanation']}"
        if hints:
            answer += f"\n\nIf you share your {' and '.join(hints)}, I can refine this offer further."

        return answer, tool_calls, recommendation, guardrail_result, workflow, borrower

    async def _load_history(self, conv_id: UUID, limit: int = 10) -> list[dict]:
        rows = (
            await self.session.execute(
                select(AgentMessage)
                .where(AgentMessage.conversation_id == conv_id)
                .order_by(AgentMessage.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return [
            {
                "role": r.role,
                "content": r.content,
                "intent": r.intent,
                "metadata": r.metadata_json,
            }
            for r in reversed(rows)
        ]

    async def _save_message(
        self, conv_id: UUID, role: str, content: str, intent: str | None = None, metadata: dict | None = None
    ) -> None:
        self.session.add(
            AgentMessage(
                message_id=uuid4(),
                conversation_id=conv_id,
                role=role,
                content=content,
                intent=intent,
                metadata_json=metadata,
            )
        )
        await self.session.flush()

    async def _conversational_reply(
        self,
        message: str,
        history: list[dict],
        role: str,
        tool_context: dict | None,
        intent: str,
    ) -> str | None:
        if not self.client:
            return None
        history_text = ""
        for msg in history[-6:]:
            history_text += f"{msg['role'].upper()}: {msg['content']}\n"

        context_block = ""
        if tool_context:
            context_block = f"\nTool results (use these exact numbers):\n{json.dumps(tool_context, default=str)[:4000]}"

        if intent == "greeting":
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"User role: {role}\n"
                f"Conversation so far:\n{history_text}\n"
                f"User: {message}\n\n"
                f"Respond warmly and briefly. If they seem ready to work, offer to help with settlements, portfolio analytics, or policies."
            )
        else:
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"User role: {role}\n"
                f"Conversation so far:\n{history_text}\n"
                f"{context_block}\n"
                f"User: {message}\n\n"
                f"Write a conversational response using the tool results above. Keep all numbers exact. "
                f"Refer to borrowers as Legal Name (customer_code)."
            )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
            )
            return response.text
        except Exception:
            return None

    def _fallback_reply(self, intent: str) -> str:
        if intent == "greeting":
            return (
                "Hello! I'm your Decision Intelligence assistant. "
                "I can help with settlement recommendations, portfolio KPIs, policy questions, and what-if scenarios. "
                "Share a customer **name** and **code** to get started."
            )
        return "I processed your request but couldn't generate a full response. Please try rephrasing your question."

    def _format_portfolio(self, data: dict) -> str:
        kpis = data.get("kpis", {})
        segments = data.get("segments", [])
        lines = [
            f"Portfolio EV: £{kpis.get('total_expected_value', 0):,.0f}",
            f"Actual Collections: £{kpis.get('total_collections', 0):,.0f}",
            f"Realization Rate: {kpis.get('realization_rate', 0)*100:.1f}%",
            f"Borrowers: {kpis.get('borrower_count', 0)}",
            "\nSegment Performance:",
        ]
        for s in segments:
            lines.append(
                f"- {s['segment']}: {s['borrower_count']} borrowers, EV £{s['total_ev']:,.0f}, "
                f"avg P(Fulfill) {s['avg_p_fulfillment']*100:.0f}%"
            )
        return "\n".join(lines)

    def _format_monitoring(self, data: dict) -> str:
        alerts = data.get("alerts", [])
        lines = ["Model Health Summary:\n"]
        for m in data.get("metrics", []):
            flag = " [ALERT]" if m.get("alert_flag") else ""
            lines.append(f"- {m['model_name']} {m['metric_name']}: {m['metric_value']} (baseline {m['baseline_value']}){flag}")
        if alerts:
            lines.append(f"\n{len(alerts)} alert(s) require attention.")
        return "\n".join(lines)

    def _format_frontier(self, data: dict) -> str:
        lines = ["Efficient Frontier:\n"]
        for f in data.get("frontier", []):
            lines.append(f"- {f['strategy_name']}: EV £{f['portfolio_ev']:,.0f}, Risk {f['risk_level']}")
        sim = data.get("simulation", {})
        if sim:
            lines.append(
                f"\nScenario (MILP): Portfolio EV {sim.get('baseline_portfolio_ev')} → {sim.get('constrained_portfolio_ev')} "
                f"({sim.get('ev_change_percent')}%) | solver {sim.get('solver_status')}"
            )
        return "\n".join(lines)

    def _format_explain(self, display: str, data: dict) -> str:
        lines = [f"Here's what's driving the model's prediction for **{display}**:\n"]
        lines.append("**Top positive drivers** (increase acceptance likelihood):")
        for f in data.get("top_positive", []):
            lines.append(f"- {f['feature_name']} ({f['shap_value']:+.3f})")
        lines.append("\n**Top negative drivers** (decrease acceptance likelihood):")
        for f in data.get("top_negative", []):
            lines.append(f"- {f['feature_name']} ({f['shap_value']:+.3f})")
        return "\n".join(lines)

    def _fallback_document_answer(self, rag_result: dict) -> str:
        sources = rag_result.get("sources", [])
        if not sources:
            return "I couldn't find any relevant policy documents for that question. Could you rephrase or specify which policy area you're interested in?"
        top = sources[0]
        return f"Based on **{top['document_name']}**:\n\n{top['content'][:500]}"
