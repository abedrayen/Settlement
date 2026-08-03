# Prompt for Cursor: Settlement Portfolio Intelligence Agent — Views, Roles, Functionality, UI/UX

## Context for the build agent
This is a conversational AI platform for a collections/recoveries business. It sits on top of three predictive models (PoAPP, PoA/PoC, PoF) and an MILP optimizer, and lets users ask natural-language questions about a settlement portfolio instead of running notebooks. Build the frontend (chat-first, React) against this spec. Treat every screen as a *view onto the same agent conversation* — this is not a multi-app dashboard with a chatbot bolted on; the chat is the spine, and structured views are things the agent renders or that a user pins/expands from a chat response.

---

## 1. Roles

| Role | Who | What they need | Access level |
|---|---|---|---|
| **Collections Analyst** | Works individual borrower accounts day to day | Fast single-borrower lookups, optimal offer + rationale, ability to act on a recommendation | Full chat + borrower-level views; cannot change guardrail thresholds |
| **Portfolio Manager** | Owns portfolio-level performance and strategy | Aggregate KPIs, EV vs actual, cohort-level what-ifs, efficient frontier | Full chat + portfolio-level views; can run frontier simulations |
| **Senior Stakeholder** | Wants directional answers, not mechanics | High-level summaries, trend answers, minimal UI chrome | Full chat, read-only on structured views, no export/action buttons needed but not blocked either |
| **Compliance Reviewer** | Needs to independently verify any recommendation | Audit trail, raw numbers behind an answer, model version/vintage, guardrail pass/fail history | Read-only across everything + exclusive access to the full audit log view |
| **Admin** | Platform owner/ops | Data refresh status, model version history, guardrail rule configuration | Full access + settings view |

Design the UI so role is a lens on the same underlying app — don't build five separate apps. Nav and available panels adjust by role; the chat itself behaves identically for everyone except that guardrail-blocked or compliance-sensitive detail is always visible (never hidden by role — only *editing* is role-gated).

---

## 2. Information architecture (top-level views)

1. **Agent (Chat)** — default landing view, primary interface
2. **Portfolio Performance** — dashboard view, pinnable from chat or opened directly
3. **Borrower / Settlement Assignment** — single-borrower detail view
4. **Economic Terms Simulator** — efficient frontier + constraint sandbox
5. **Audit Trail** — compliance-facing log of every recommendation and tool call
6. **Settings / Admin** — data freshness, model versions, guardrail config (Admin only)

Global layout: persistent left nav with these six items, a persistent chat panel (collapsible to a side rail when a structured view is open, expandable to full width by default), and a top bar showing current data vintage / last refresh timestamp at all times — this last element is not optional, it's a trust signal that must always be visible.

---

## 3. View-by-view functionality

### 3.1 Agent (Chat) — primary view
- Standard chat thread: user message, agent response.
- Agent responses are **mixed-media**, not plain text: a response can contain a text explanation, an inline structured table, an inline mini-chart (e.g. frontier curve, EV trend), and action chips (e.g. "View full borrower record," "Download CSV," "Show SHAP breakdown").
- Every model-derived number in a response carries a small **confidence indicator** (inline badge) — hover/tap reveals P(x) std, MIP gap, vintage, and an out-of-distribution flag if applicable. This is not optional UI polish — it's a required behavior per response, not per-view.
- If a response involves a recommendation that passed through the guardrail layer, show a small "Guardrail: passed" affirmative tag. If a guardrail would have blocked a recommendation, the agent must say so explicitly in the message — never silently omit a blocked answer.
- Multi-turn context is visually traceable: if a follow-up question references "these borrowers" or "that offer," lightly highlight or reference the earlier message it's chaining from, so users can see the thread of reasoning, not just trust it.
- Streaming responses (token-by-token or block-by-block) with a lightweight loading state while a tool call (especially the MILP solver, ~2s) is running — show *what's happening* ("Running optimizer for borrower 243445…"), not a generic spinner.
- Left-nav "New chat" plus a searchable chat history sidebar, since repeated questions should be fast to re-find (this also mirrors the long-term memory/vector-store retrieval behavior on the backend).

### 3.2 Portfolio Performance
- KPI summary cards at top: current EV vs actual, realisation rate, trend delta (this month vs last).
- Time-series chart: EV / realisation rate over time, filterable by date range and portfolio segment (e.g. "3L").
- Drift/monitoring panel: flags from `monitoring_baselines.json` — visually distinct (warning color) when a KPI has drifted outside baseline.
- Every chart/table has a "download" affordance (CSV/parquet) and an "ask the agent about this" affordance that opens chat pre-filled with a relevant question about the selected data point.
- This view can be reached two ways: direct nav click, or the agent pinning/expanding it from a chat answer — the same component should render in both contexts.

### 3.3 Borrower / Settlement Assignment
- Borrower search/lookup at top (by ID).
- Borrower summary panel: account status, outstanding balance, application/payment history summary.
- **Optimal offer panel**: the MILP-recommended settlement terms for this borrower, with the EV calculation shown explicitly (`EV = APP × PoA × PoF × Settlement Amount`, each factor visible, not just the final number).
- **Offer grid comparison**: a table or chart letting the user see the scored alternatives (e.g. 60% RR vs 40% RR) side by side, so "why did the optimizer choose X over Y" is visually answerable, not just a text explanation.
- **Explain this score** action → opens the SHAP explainer panel (T6) showing top contributing features for the selected P(x) score, ranked, with direction (pushing score up/down).
- Guardrail status block: explicit pass/fail on RR-limit and deceased/legal-entity checks for this borrower, always visible on this view (not just when there's a problem).

### 3.4 Economic Terms Simulator
- Efficient frontier chart (risk/reward curve) as the centerpiece.
- Constraint controls (sliders/inputs) — e.g. "P(fulfil) ≥ [value]" — that let a portfolio manager re-run a what-if and see the frontier shift and the resulting total-EV delta.
- Before/after comparison: total EV under current strategy vs under the simulated constraint, shown as a clear delta, not just two separate numbers to mentally subtract.
- Batch/portfolio-wide runs should show a job-status indicator (queued/running/done) since these are async, unlike single-borrower queries — never let this view imply an instant result for a portfolio-scale run.
- Results here should be shareable back into chat ("ask the agent to explain this frontier shift") to keep the chat as the reasoning spine.

### 3.5 Audit Trail (Compliance Reviewer + Admin)
- Chronological, filterable log: every tool call, its inputs, its outputs, timestamp, initiating user, model version tag, data vintage.
- Each entry expandable to show the raw numbers that generated a given chat answer, so a reviewer can reconstruct it independently of the LLM.
- Guardrail decisions logged distinctly (pass/fail with the rule that fired), searchable separately from general tool calls.
- Export capability for compliance reporting.

### 3.6 Settings / Admin
- Data source status: last refresh timestamp per source, cadence (real-time/weekly/monthly/quarterly), staleness warning if a source is overdue for refresh.
- Model version history: current PoAPP/PoA/PoF/RSF bundle versions, retrain date, and a way to see which chat answers were generated under a prior version.
- Guardrail rule configuration (RR limits, flag definitions) — editable here only, never exposed as an editable surface anywhere else in the app.

---

## 4. Core reusable UI components (build these once, use everywhere)

- **Confidence badge** — small inline indicator (P(x) std / MIP gap / vintage / OOD flag), consistent across chat, borrower view, and portfolio view.
- **Guardrail status tag** — pass/fail/blocked, consistent styling wherever a recommendation appears.
- **EV breakdown chip** — the `APP × PoA × PoF × Amount` decomposition, reusable in chat responses and the borrower view.
- **Data-vintage strip** — persistent top-bar element showing "as of" freshness for whatever data is currently in view.
- **Downloadable table** — any structured table in chat or a dashboard should support CSV/parquet export, not just view-only.
- **"Ask the agent" bridge** — a button on any chart/table/card that opens chat pre-filled with a context-aware question about that exact data point, so structured views always route back into the conversational spine rather than becoming dead ends.

---

## 5. Representative use cases (map directly to the spec's example questions)

**UC1 — Single-borrower optimal offer**
> "What is the optimal offer for borrower 243445?"
- User types in chat → agent resolves borrower (T1) → retrieves offer grid (T2) → returns optimizer result (T3) with EV breakdown, confidence badges, and guardrail status inline → user can click "View full borrower record" to land on 3.3 with the same data expanded.

**UC2 — Why-this-not-that**
> "Why did the optimiser choose 60% RR over 40%?"
- Follow-up in the same thread → agent pulls the offer-grid comparison (T2) and, if asked further, the SHAP explanation (T6) → renders the comparison table inline in chat and offers "Explain this score" to open the explainer panel.

**UC3 — Portfolio trend**
> "What is the current 3L EV vs actual? How has realisation rate moved this month?"
- Agent calls the KPI/monitoring tool (T4) → renders a compact trend chart + numbers directly in chat, with a "pin to Portfolio Performance" action to open 3.2 for deeper exploration.

**UC4 — Constraint what-if**
> "What happens to total EV if we apply a P(fulfil) ≥ 0.70 floor? Show me the efficient frontier."
- Agent runs the frontier/constraint tool (T5) → for a portfolio-wide run, this may be async — chat shows a job-status message, then the result renders as a frontier chart with a before/after EV delta, and a link into 3.4 for interactive adjustment.

**UC5 — Multi-turn chained reasoning**
> "Show me the top 5 borrowers where switching from 2-instalment to 1-instalment would gain the most EV."
- Agent chains T3 → T2 → T6 across the exchange, holding context; UI shows a ranked table of 5 borrowers inline in chat, each row clickable into 3.3, with the reasoning trace visually linkable back through the conversation (per 3.1's "traceable multi-turn context" requirement).

**UC6 — Compliance reconstruction**
> A compliance reviewer wants to verify a recommendation given to an analyst last week.
- Reviewer opens Audit Trail (3.5), filters by borrower/date, expands the entry to see raw inputs/outputs, model version, and guardrail decision — no dependency on re-asking the agent or trusting the original chat answer.

---

## 6. Interaction & state behavior notes for Cursor

- Treat every chat response as potentially long-running (tool calls, especially T3/T5, are not instant) — design loading and partial-result states, don't assume synchronous request/response everywhere.
- Never render a model-derived number without its confidence badge — this should be enforced at the component level (e.g. a `<ModelValue>` component that requires a confidence prop), not left to per-screen discipline.
- Guardrail-blocked outcomes are a first-class UI state, not an error state — style and copy them as "this recommendation was withheld because…", never as a generic failure.
- Keep the chat panel persistent and reachable from every structured view — no view should be a dead end that requires backing out to get back to the conversation.
- Role changes what's editable and what's navigable by default, not what's visible on a given record — compliance-relevant detail (guardrail status, model version, raw numbers) stays visible to every role that can see the underlying recommendation at all.

## 7. Out of scope for this UI pass
- Slack bot UI (separate surface, same backend — not part of this build).
- Guardrail rule *logic* (only the admin config surface is in scope here; the rules themselves are backend).
- Document-intelligence UI (flagged in the spec as a possible future connection — leave a clean extension point in the nav/IA but don't build it now).