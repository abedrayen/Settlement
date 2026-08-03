# Settlement Portfolio Intelligence Agent — Specification Checklist

> **Last indexed:** 2026-08-03 after Decision Engine + Agent/HITL (simulated) implementation.
>
> **Status legend**
> - `[x]` **Done** — implemented and usable in the MVP
> - `[~]` **Partial** — present as demo/simulation, seeded data, or incomplete vs production intent
> - `[ ]` **Not started** — missing from the codebase
>
> **MVP verdict:** End-to-end demo with **PuLP MILP** offer/portfolio optimization, **simulated ModelScorer (T5)**, expanded chat intents (name+code identity), and HITL approval workflows. Live `.pkl` models, parquet ETL, SSO, and multi-channel remain out of scope. See `docs/SYSTEM_DOCUMENTATION.md`.

| Area | Done | Partial | Not started |
|---|---|---|---|
| 1. Business objectives | 6 | 3 | 1 |
| 2. Decision engine pipeline | 14 | 10 | 1 |
| 3. Core tools T1–T6 | 5 | 1 | 0 |
| 4. Data & model assets | 0 | 6 | 2 |
| 5. LLM orchestration layer | 1 | 9 | 5 |
| 6. Operating model questions | 0 | 0 | 11 |
| 7. Component responsibilities | 3 | 6 | 0 |
| 8. Conversational intents | 7 | 2 | 0 |
| 9. HITL / governance | 7 | 3 | 1 |
| 10. Roles, KPIs & dashboards | 2 | 3 | 0 |

---

## 1. Business Objectives
- [x] Conversational AI agent for collections analysts, portfolio managers, and senior stakeholders — *SSE chat + 5 JWT roles*
- [~] Instant, model-grounded answers about the settlement portfolio — *simulated scorer + seeded SHAP/grid; not live `.pkl`*
- [x] Replace ad-hoc notebook/Excel runs with natural-language interface — *demo NL interface exists*
- [ ] Backed by live modelling infrastructure
- [x] Use three-stage probability chain + Expected Value (EV) + MILP optimization — *shared `scoring.py` + PuLP CBC*
- [x] Optimize settlement offers — *single-borrower PuLP MILP over offer grid*
- [x] Maximize portfolio Expected Value — *portfolio PuLP assignment + frontier constraint sim*
- [x] Provide explainable recommendations — *SHAP tool + recommendation cards*
- [~] Enable real-time scenario analysis — *frontier/portfolio MILP what-if via chat + Strategy UI*
- [x] **Explicit constraint: LLM does not make business decisions** — it only explains/communicates decision-engine outputs — *enforced in `SYSTEM_PROMPT` + tool routing*

## 2. Decision Engine Pipeline (6 stages)
1. **Borrower Data Collection**
   - [x] Customer profile — *`dim_customer` + borrower APIs/UI; chat resolves **legal name + customer code***
   - [x] Payment history — *seeded `fact_payments` + `payment_history` chat intent*
   - [ ] Transaction history
   - [~] Financial indicators — *balance, RR, settlement fields in seed/profile*
   - [~] Behavioral attributes — *flags, segment, vulnerability/OOD markers*
2. **Predictive Models** — three-stage probability chain
   - [~] PoAPP: Contact → Application — *`ModelScorer` / `score_probabilities` (simulated, deterministic)*
   - [~] PoA: Application → Acceptance — *same*
   - [~] PoF: Acceptance → Fulfillment — *same*
   - [x] Combined output: probability of successful recovery — *product used inside EV*
3. **Expected Value Logic**
   - [x] Formula: EV = PoAPP × PoA × PoF × Settlement Amount — *`app/services/scoring.py`*
   - [x] Optimize for EV, not just recovery rate — *MILP maximizes EV*
4. **Optimization Engine (MILP)**
   - [x] Test all possible offer combinations (grid) — *PuLP binary select over 3×3 grid*
   - [x] Vary recovery rates and installment structures — *seeded grid + constraints*
   - [x] Select best global portfolio outcome — *`optimize_portfolio` PuLP*
   - [~] Constraints: budget limits, business rules, capacity constraints, time constraints — *RR bounds, min P(fulfill), max avg RR, installment-share capacity; no time/budget $ yet*
5. **Offer Grid**
   - [x] Installment plan proposals
   - [x] Discount scenarios — *via recovery-rate combos*
   - [x] Alternative settlement options — *top-3 alternatives on recommendation*
   - [x] Expected value per offer
6. **AI Agent Interface**
   - [x] Scenario simulation — *strategy/frontier + portfolio MILP chat*
   - [x] Explainable recommendations
   - [x] Decision support — *recommend + guardrail + approval/escalation*
   - [~] Business insights — *portfolio KPIs/segments via chat + UI*
   - [x] Core domains: Portfolio Monitoring, Settlement Optimization, Economic Terms Analysis

**Target business value:** ↑ recovery rate, ↓ decision time, ↑ consistency, ↑ transparency, ↑ scalability — *demo only; not measured in production*

## 3. Architecture — Six Core Tools/Services
- [x] **T1 BorrowerLookup** — fetch profile + scores — *`ToolService.borrower_lookup`*
- [x] **T2 OfferOptimiser** — run MILP for 1 or N borrowers — *PuLP CBC single + portfolio*
- [x] **T3 PortfolioMonitor** — query KPI snapshots — *`portfolio_analytics` + `/api/portfolio/*`*
- [x] **T4 FrontierAnalyser** — run/retrieve efficient frontier — *seeded frontier + portfolio MILP constraint sim*
- [~] **T5 ModelScorer** — run PoApp / PoC / RSF on demand — *simulated deterministic scorer + `POST /api/borrowers/{id}/score`*
- [x] **T6 ExplainerTool** — SHAP feature contributions — *seeded SHAP rows + explainability tool*

## 4. Data & Model Assets (with refresh cadence)
| Source | Role | Refresh | Status |
|---|---|---|---|
| [~] prescored_borrower_offer_grid.parquet | Pre-computed borrower/offer pair scores | Monthly re-score | **Postgres** `fact_offer_grid_scores` via seed (no parquet/ETL) |
| [~] recommended_offers_3l_v3.parquet | Latest MILP optimal assignments | Monthly re-run | **Postgres** recommended offers seeded; runtime MILP can re-assign |
| [~] monitoring_baselines.json | KPI snapshots for drift detection | Monthly | Seeded monitoring metrics + static settings freshness |
| [~] ApplicationsDataset_UPD.parquet | ApplicationCode → CustomerCode bridge + offer history | Weekly | `bridge_mapping` / related seed tables |
| [~] PaymentsDataset.parquet | Payment history for PoApp feature engineering | Weekly | `fact_payments` seeded |
| [ ] Model bundles (.pkl) | PoApp, PoC GBM, RSF | Quarterly retrain | Absent — versions are display metadata only |
| [~] efficient_frontier_3l_v3.csv | Pre-computed risk/reward curve | Monthly | `fact_efficient_frontier` seeded |
| [ ] CRM / contact system | Live contact attempts, RPC outcomes | Real-time | Absent |

## 5. LLM Orchestration Layer Requirements
- [~] Identity & Access Management: SSO (SAML/OAuth2), MFA, RBAC, JWT — *JWT + RBAC + 5 roles; no SSO/MFA*
- [ ] Edge & security: WAF/DDoS protection, API gateway, rate limiting, TLS/SSL
- [~] AI Agent Service: intent recognition, conversation manager, session/state management, tool/function calling, response generation — *expanded keyword intents + Gemini polish; name+code slot filling*
- [x] LLM (GPT-5.5/4o or equivalent) — *Google Gemini (`google-genai`)*
- [~] Knowledge Base (policies, FAQs, guides) — *`content/docs/*.md`*
- [~] RAG Engine (vector search/retrieval) + Vector Database — *pgvector schema + **hash pseudo-embeddings***
- [~] Tool Orchestrator: tool registry, tool execution, result parser, error handling — *`ToolService` + orchestrator routing*
- [~] Rule Engine (business rules) — *`GuardrailEngine` + approval risk tiers in `guardrail_config.json`*
- [~] Workflow Engine (processes & approvals) — *approve/reject/escalate + queues; not full BPM*
- [~] Integration Layer: REST API, SOAP, GraphQL, gRPC, Kafka/MQ, ESB/Adapter — *REST/SSE only*
- [ ] Backend system connections: CRM, billing, debt management, settlements, payments, notification service, document management
- [~] Platform services: PostgreSQL, Redis (cache/session), object storage, secrets manager, CI/CD, backup & DR — *Postgres + Docker Compose only*
- [~] Observability & Governance: monitoring/metrics, logging, distributed tracing, audit trail, alerts — *audit trail + seeded model monitoring UI*
- [ ] External system connectivity: VPN/Private Link/ExpressRoute
- [~] Multi-channel support: web chat, mobile app, WhatsApp, Viber, voice/IVR, email, SMS — *web chat only*

## 6. Operating Model — Open Questions to Resolve (11)
1. [ ] Decision Ownership — what AI, Rule Engine, Manager, Executive each decide
2. [ ] Exception Handling — fallback flows, degraded mode, retry/compensation, conflict resolution
3. [ ] Data Quality & Completeness — missing data handling, mandatory vs optional fields, validation rules
4. [ ] Policy Lifecycle — versioning, ownership, controlled updates
5. [ ] Compliance & Auditability — why/who approved/which policy version, immutable logs — *audit + resolved_by notes exist; policy-version governance unresolved*
6. [ ] Latency & Performance — max response per intent, sync vs async, caching, timeout fallback
7. [ ] Human Workload (HITL) — queue prioritization, batching, auto-approval thresholds, balancing
8. [ ] Risk Stratification — low/med/high routing, dynamic thresholds, behavioral scoring — *config-driven tiers implemented; org policy TBD*
9. [ ] Feedback Loop — learning from overrides, rejected suggestions, outcomes, customer behavior
10. [ ] Failure Modes — LLM hallucination, rule vs workflow conflict, integration downtime
11. [ ] Organizational Alignment — who owns rules, workflows, data, AI behavior

## 7. System Component Responsibilities
- [x] **AI Agent Service** — understands intent, keeps flow, requests missing info (name + code), does NOT decide
- [x] **Tool Orchestrator** — calls APIs, manages execution, handles API errors, returns LLM-ready structured results
- [~] **Rule Engine** — guardrails + RR bounds + approval thresholds; no full settlement calculator
- [~] **RAG Engine** — policy docs + pseudo-embeddings
- [~] **Integration Layer** — internal REST only
- [x] **Workflow Engine** — approvals & escalations with approve/reject/escalate + resolution notes
- [~] **IAM/Security Layer** — JWT RBAC; workflows/documents gated
- [~] **Observability & Audit** — recommendation/tool audit + export
- [~] **LLM (GPT)** — Gemini polishes; routing is keyword-based

## 8. Conversational Design — 8 Required Intents
| # | Intent | Required Data | Status |
|---|---|---|---|
| 1 | Debt restructuring / installment plan | Customer name + code, debt, optional installments/capacity | [x] `restructuring` intent + MILP; optional slot prompts |
| 2 | Debt inquiry | Customer name + code | [x] `debt_inquiry` |
| 3 | Payment history | Customer name + code | [x] `payment_history` |
| 4 | Decision explanation | Customer name + code | [x] `decision_explanation` / SHAP |
| 5 | Re-negotiation | Customer + constraints | [x] `renegotiation` with RR/installment filters |
| 6 | Policy/exception request | Customer + reason | [x] `policy_exception` → workflow + RAG |
| 7 | Guidance/recommendation | Customer name + code | [x] MILP recommendation + approval routing |
| 8 | Human handoff | Reason + conversation | [x] `human_handoff` workflow task |

- [x] Missing Data Strategy defined: prompts for **customer name and customer code**; disambiguates multi-name matches as `Name (code)`
- [x] Flow: Intent → Required Data → Tool Calls → Rule Engine → Response
- [x] Borrower display format: always **`Legal Name (customer_code)`** in chat, cards, workflows

## 9. Human-in-the-Loop / Governance — 10 Questions the System Must Answer
1. [x] What decision is recommended and why (rule, data, policy used) — *EV offer + SHAP + model version + solver status*
2. [x] Is this within allowed limits (rule violation, exception, borderline case) — *`within_limits` on recommendation*
3. [x] Does this require human approval (thresholds, high-risk, manual-only) — *risk tier + `requires_approval`*
4. [x] Who should approve it (supervisor/agent/risk team, region/role routing) — *`approver_queue` (manager/compliance/specialist)*
5. [x] What alternative options exist (stricter/flexible arrangement, reject/defer/renegotiate) — *top-3 grid alternatives*
6. [~] What happens if approved or rejected (system changes, customer impact, triggered workflow) — *workflow status + note; no downstream system writes*
7. [x] How risky is this decision (credit risk, payment probability, historical behavior) — *`risk_tier` + P(fulfill)*
8. [~] What data is missing for a safe decision (income, contract, identity verification) — *name/code prompts; not full missing-data matrix*
9. [x] Is it compliant with policy/regulation (legal constraints, internal policy, regulatory rules) — *guardrails + policy RAG*
10. [x] What explanation will the customer see (simple, understandable, defensible) — *`customer_explanation` on recommendation*
- [~] Approval decision tree with escalation paths (yes/no) — *implemented in `GuardrailEngine.classify_decision` + Workflows UI*

## 10. Roles, KPIs & Dashboards

**Manager (Operational)**
- [~] KPIs: approval rate, escalation volume/day, SLA compliance, policy exception rate, agent performance score, avg resolution time/case — *workflows inbox supports ops review; checklist KPIs not fully instrumented*
- [x] Dashboard: pending approvals queue, escalated cases w/ reason — *`/workflows` with Approve/Reject/Escalate; Documents/Monitoring in nav*

**Upper Management (Strategic)**
- [~] KPIs: total recovery rate, automation rate, cost per case, portfolio risk distribution, … — *portfolio EV/realization/segments; most exec KPIs absent*
- [~] Executive Dashboard: partial via `/portfolio` + `/strategy`

**Decision-making split**
- [x] AI Agent → executes conversation + gathers data (name + code)
- [x] Manager → validates operations + handles exceptions — *approval actions in Workflows*
- [~] Executive → monitors strategy + optimizes system performance — *stakeholder role + portfolio/strategy views*

---

## Implementation notes (2026-08-03 A+B)

| Deliverable | Evidence |
|---|---|
| Shared scoring | `backend/app/services/scoring.py` |
| Simulated T5 | `backend/app/services/model_scorer.py`, `POST /api/borrowers/{id}/score` |
| PuLP MILP T2 | `backend/app/services/optimizer.py` (single + portfolio) |
| Approval tree | `backend/content/guardrail_config.json`, `GuardrailEngine.classify_decision` |
| Name + code chat | `AgentOrchestrator._resolve_borrower` |
| HITL UI | `/workflows` Approve/Reject/Escalate; sidebar Workflows/Documents/Monitoring |

Want this exported as a Word or Excel checklist/tracker (with owner/status columns) instead of inline markdown?
