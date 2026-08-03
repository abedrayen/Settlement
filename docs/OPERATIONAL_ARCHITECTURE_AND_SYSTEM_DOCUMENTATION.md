# Settlement Portfolio AI Agent — Operational Architecture & System Documentation

| Field | Value |
|-------|-------|
| **Document title** | Operational Architecture & System Documentation |
| **Product** | Settlement Portfolio AI Agent (Decision Intelligence Layer) |
| **Version** | 1.0 (as-built MVP) |
| **Repository root** | `MVP/` |
| **Audience** | Software engineers, QA engineers, product owners, auditors, technical architects |
| **Authority** | Describes the system **as implemented** in this repository. Aspirational enterprise features from pitch decks are called out explicitly as *not implemented*. |
| **Related references** | `README.md`, `Settlement_Portfolio_Intelligence_Agent.md`, `content/decision-intelligence-agent-specification.md`, `content/database-schema.md`, `docs/SYSTEM_DOCUMENTATION.md` |

---

## Table of Contents

1. [Purpose and Scope](#1-purpose-and-scope)
2. [Business Context and Domains](#2-business-context-and-domains)
3. [System Context and Boundaries](#3-system-context-and-boundaries)
4. [Logical Architecture](#4-logical-architecture)
5. [Physical Deployment Architecture](#5-physical-deployment-architecture)
6. [Technology Stack](#6-technology-stack)
7. [Component Catalog and Interactions](#7-component-catalog-and-interactions)
8. [Data Architecture](#8-data-architecture)
9. [Decision Engine](#9-decision-engine)
10. [Agent Orchestration](#10-agent-orchestration)
11. [Guardrails, Compliance, and HITL](#11-guardrails-compliance-and-hitl)
12. [End-to-End Business Workflows](#12-end-to-end-business-workflows)
13. [Security, Identity, and Authorization](#13-security-identity-and-authorization)
14. [API Surface](#14-api-surface)
15. [Frontend Information Architecture](#15-frontend-information-architecture)
16. [Configuration and Secrets](#16-configuration-and-secrets)
17. [Operations Runbook](#17-operations-runbook)
18. [Observability, Performance, and Limits](#18-observability-performance-and-limits)
19. [Testing and Quality Assurance](#19-testing-and-quality-assurance)
20. [As-Built vs Target Architecture](#20-as-built-vs-target-architecture)
21. [Glossary](#21-glossary)
22. [Appendix — Repository Map](#22-appendix--repository-map)

---

## 1. Purpose and Scope

### 1.1 What the platform is

The Settlement Portfolio AI Agent is a **Decision Intelligence Layer** for debt settlement portfolios. It gives collections analysts, operational managers, and administrators a single governed surface to:

- Inspect borrower settlements, payment history, and offer grids
- Obtain **model-backed settlement recommendations** (Expected Value / probability chain)
- Run **constrained optimization** (single borrower and portfolio) via PuLP CBC MILP
- Enforce **compliance guardrails** and route edge cases into **human-in-the-loop (HITL)** approval queues
- Ask policy questions against ingested regulatory / model-card documents (RAG)
- Audit recommendations, tool calls, and workflow resolutions

The product thesis is: *ask a question in plain English and receive a model-backed, compliance-gated answer*, with dashboards for the same decision objects when conversational interaction is not enough.

### 1.2 What this document covers

| In scope | Out of scope |
|----------|--------------|
| All runtime components in `backend/`, `frontend/`, `content/docs/`, `docker-compose.yml` | Future CRM/billing/Kafka integrations described only in pitch material |
| Data model, seed strategy, EV math, MILP, guardrails, RBAC | Live `.pkl` model training pipelines (not present) |
| How UI views, APIs, orchestrator, tools, and Postgres interact | Multi-tenant SaaS / cloud production topology (not present) |
| Operational startup, reseed, re-ingest, reset procedures | Formal SLA / DR contracts (not defined) |

### 1.3 How to use this document by role

| Role | Start here |
|------|------------|
| **New engineer** | §§3–7, then §10–12, then Appendix |
| **QA** | §§12, 14–15, 19; demo scenarios in §12.6 |
| **Product owner** | §§1–2, 12, 15, 20 |
| **Auditor** | §§8–9, 11, 13; audit tables and workflow lifecycle |
| **Architect** | §§3–7, 9–11, 18, 20 |

---

## 2. Business Context and Domains

### 2.1 Problem domain

Debt settlement operations traditionally split work across predictive models, optimization notebooks, policy PDFs, and manual escalation. This platform collapses those into:

1. **Borrower decisioning** — which recovery rate (RR) and installment plan maximize Expected Value (EV) under policy
2. **Portfolio strategy** — how to assign offers across many borrowers under RR / fulfillment constraints (efficient frontier / MILP)
3. **Governance** — hard blocks, soft warnings, manager approval, specialist queues, full audit trail

### 2.2 Personas (as implemented)

| Role key | Display label | Primary job |
|----------|---------------|-------------|
| `analyst` | Collection Analyst | Work borrower cases, chat for recommendations, read frontier; cannot approve workflows or run portfolio MILP jobs |
| `manager` | Operational Manager | Portfolio/executive views, approve/reject/escalate, run strategy jobs, audit |
| `admin` | Admin | Everything manager can do, plus settings (guardrails, models) |

Legacy role names (`stakeholder`, `compliance`, `executive`) are **normalized to `manager`** in both backend and frontend.

### 2.3 Core business formula

\[
\mathrm{EV} = \mathrm{PoAPP} \times \mathrm{PoA} \times \mathrm{PoF} \times (\mathrm{Balance} \times \mathrm{RR})
\]

| Symbol | Meaning |
|--------|---------|
| **PoAPP** | Probability of application (borrower applies for the settlement) |
| **PoA** | Probability of acceptance (offer accepted) |
| **PoF** | Probability of fulfillment (plan is completed / kept) |
| **Balance** | Outstanding connected-loan / settlement balance used as base |
| **RR** | Recovery rate (settlement amount ÷ balance) |

Implemented in `backend/app/services/scoring.py` and shared by seeding and runtime ModelScorer so demo scores stay consistent.

### 2.4 Offer design space

Each borrower has a **3 × 3 offer grid**:

| Recovery rates | Installment counts |
|----------------|--------------------|
| 20%, 40%, 60% (seeded grid cells) | 1, 2, 3 |

= **9 scored offers** per customer in `fact_offer_grid_scores`. Policy RR envelope is **20%–80%** (`guardrail_config.json` + `recovery-rate-policy.md`). Optimization selects among feasible cells; it does not invent off-grid RR/installment pairs.

---

## 3. System Context and Boundaries

### 3.1 Context diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Actors (Browser)                                  │
│   Analyst · Manager · Admin                                              │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ HTTPS/HTTP :3000
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Presentation — Next.js 14 (App Router)                                   │
│  Auth cookie/JWT · Role-filtered nav · Six primary views + secondary     │
│  Persistent ChatPanel (SSE) · Workspace · Optimization · Approvals …     │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ REST + SSE :8000  (Bearer JWT)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Application — FastAPI                                                    │
│  Routes → Orchestrator / Repositories / Tools / Guardrails / RAG         │
│  Gemini (optional polish) · PuLP CBC MILP · Deterministic scorer         │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ asyncpg / SQLAlchemy 2
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Data — PostgreSQL 16 + pgvector                                          │
│  Dimensions · Facts · Agent audit · Workflows · Document chunks          │
└──────────────────────────────────────────────────────────────────────────┘

External (optional): Google Gemini API  ←── only for prose polishing of tool results
Local files: content/docs/*.md          ←── mounted RO into backend for RAG ingest
```

### 3.2 Trust boundaries

| Boundary | Crossing mechanism | Notes |
|----------|--------------------|-------|
| Browser ↔ Frontend | Cookie `access_token` + localStorage | Middleware redirects unauthenticated users to `/login` |
| Frontend ↔ Backend | `Authorization: Bearer` | Backend RBAC is authoritative |
| Backend ↔ Postgres | `DATABASE_URL` | Compose uses hardcoded demo credentials |
| Backend ↔ Gemini | `GEMINI_API_KEY` | If unset, template fallbacks; no LLM for EV math |
| Host ↔ Containers | Published ports 3000 / 8000 / 5432 | Local/demo only |

### 3.3 Explicit non-integrations (MVP)

The following appear in business pitch material (`settlment_portfolio.md`) but are **not implemented**: SSO/MFA/OIDC, API gateway, Kafka/message bus, CRM/billing connectors, Redis cache, email/SMS channels, object storage, Kubernetes/Terraform, CI/CD pipelines, live model artifact stores.

---

## 4. Logical Architecture

### 4.1 Layered view

```
┌─────────────────────────────────────────────────────────────────┐
│  UX Layer          Pages + Chat UI + Ask-Agent bridge           │
├─────────────────────────────────────────────────────────────────┤
│  API Layer         FastAPI routers (auth, chat, borrowers, …)   │
├─────────────────────────────────────────────────────────────────┤
│  Orchestration     AgentOrchestrator (intent → tools → polish)  │
├─────────────────────────────────────────────────────────────────┤
│  Domain Services   ToolService · GuardrailEngine · RAGService   │
│                    scoring · model_scorer · optimizer           │
├─────────────────────────────────────────────────────────────────┤
│  Persistence       Repositories + SQLAlchemy ORM + schema.sql   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Request paths (two modes)

The platform supports **two parallel access paths** to the same domain services:

| Path | Entry | Typical consumer |
|------|-------|------------------|
| **Conversational** | `POST /api/chat` (SSE) | ChatPanel / Assistant |
| **Transactional UI** | REST resource endpoints | Workspace, Optimization, Approvals, Portfolio, etc. |

Both paths ultimately call the same repositories, scoring, MILP, and guardrail logic. Chat wraps them in intent routing + Gemini polish + richer audit persistence; UI pages call tools/repos more directly via dedicated routes.

### 4.3 Control vs data plane

| Plane | Components | Responsibility |
|-------|------------|----------------|
| **Control** | JWT/RBAC, GuardrailEngine, workflow status transitions, settings JSON | Who may act; what recommendations may leave the system |
| **Data** | dim/fact tables, offer grids, frontier, monitoring, RAG chunks | Portfolio truth and model outputs (seeded / simulated) |
| **Decision** | scoring.py, optimizer.py, model_scorer.py | Compute EV and choose offers |
| **Interaction** | Orchestrator + Gemini + Chat UI | Human language over decision objects |

---

## 5. Physical Deployment Architecture

### 5.1 Docker Compose topology

Defined in `docker-compose.yml`:

| Service | Image / build | Host port | Role |
|---------|---------------|-----------|------|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | Database; schema applied on first volume init via `backend/db/schema.sql` |
| `backend` | `./backend` (Python 3.12) | 8000 | Seed DB then Uvicorn with `--reload` |
| `frontend` | `./frontend` (Node 20) | 3000 | `npm run dev` (dev server, not production build) |

**Startup sequence:**

1. Postgres becomes healthy (`pg_isready`).
2. Backend container runs `python scripts/seed_db.py` (idempotent), then `uvicorn app.main:app --reload`.
3. FastAPI **lifespan** runs inline SQL migrations (`_MIGRATE_STATEMENTS` in `main.py`) and `RAGService.ingest_documents()`.
4. Frontend starts after backend dependency (no healthcheck wait).

**Volumes:**

- `postgres_data` — persistent DB
- Backend source + `./content/docs` (read-only) mounted into the container
- Frontend source mounted; anonymous volumes for `node_modules` and `.next`

### 5.2 Process model

```
docker compose up --build
        │
        ├─ postgres  ── schema.sql (first boot only)
        │
        ├─ backend
        │     seed_db.py ──► uvicorn (lifespan: migrate + RAG ingest)
        │
        └─ frontend
              npm install && npm run dev -H 0.0.0.0
```

### 5.3 Non-Docker local development

- Backend requires **Python 3.12** (`asyncpg` wheels; Python 3.14 on Windows is unsupported per README).
- Frontend: `npm install && npm run dev`.
- Postgres with pgvector must be reachable at `DATABASE_URL`.

---

## 6. Technology Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Frontend | Next.js 14.2 (App Router), React 18, TypeScript, Tailwind, Recharts | No Redux/Zustand; Auth Context + local page state |
| Backend | FastAPI 0.115, Uvicorn, Pydantic v2 / pydantic-settings | Async throughout |
| ORM / DB | SQLAlchemy 2.0 async + asyncpg; psycopg2 for sync seed paths as needed | |
| Database | PostgreSQL 16 + pgvector | `vector(768)` on `document_chunks` |
| Auth | python-jose JWT HS256, passlib bcrypt | |
| LLM | `google-genai` (default model `gemini-3-flash-preview`) | Polish only |
| Optimizer | PuLP 2.9 + CBC | Real MILP |
| Listed unused | `langgraph`, `langchain-core` in requirements | Not imported |

---

## 7. Component Catalog and Interactions

### 7.1 Backend modules

| Module | Path | Responsibility |
|--------|------|----------------|
| App factory | `backend/app/main.py` | CORS, lifespan migrate+RAG, router mount, `/health` |
| Settings | `backend/app/config.py` | Env-driven Settings |
| DB session | `backend/app/database.py` | Async engine, `get_db` |
| Orchestrator | `backend/app/agents/orchestrator.py` | Intent classify, borrower resolve, tool routing, SSE, audit write |
| Tools façade | `backend/app/tools/service.py` | T1–T6 style tools + handoff/exception |
| Scoring | `backend/app/services/scoring.py` | PoAPP/PoA/PoF + EV |
| ModelScorer | `backend/app/services/model_scorer.py` | Simulated on-demand rescoring |
| Optimizer | `backend/app/services/optimizer.py` | Single + portfolio MILP |
| Settings store | `backend/app/services/settings_store.py` | Freshness, model registry, guardrail JSON I/O |
| Guardrails | `backend/app/guardrails/engine.py` | Evaluate + classify_decision + workflow creation |
| Repositories | `backend/app/repositories/borrower.py` | Borrower / Portfolio / Frontier / Monitoring data access |
| RAG | `backend/app/rag/service.py` | Ingest chunks, hash embed, cosine top-k |
| Auth | `backend/app/auth/security.py`, `rbac.py` | Hash/JWT; role permissions |
| ORM | `backend/app/models/entities.py` | Entity mirror of schema |
| Routes | `backend/app/api/routes/*.py` | REST surface |
| Seed | `backend/scripts/seed_db.py` | Synthetic portfolio + users |
| Validate | `backend/scripts/validate_hero.py` | EV math smoke check (no DB) |
| Guardrail config | `backend/content/guardrail_config.json` | RR bounds, approval thresholds, optimizer knobs |

### 7.2 Frontend modules

| Module | Path | Responsibility |
|--------|------|----------------|
| Root layout | `frontend/app/layout.tsx` | AuthProvider → ClientLayout |
| Middleware | `frontend/middleware.ts` | Cookie gate → `/login` |
| Auth | `frontend/components/AuthProvider.tsx` | Login/logout, token storage, `/api/auth/me` |
| Shell | `frontend/components/ClientLayout.tsx` | Sidebar, DataVintageStrip, ChatPanel, path permission redirect |
| Nav | `frontend/components/Sidebar.tsx` | Role-filtered navigation |
| API client | `frontend/lib/api.ts` | Bearer fetch + SSE `chatStream` |
| RBAC mirror | `frontend/lib/roles.ts` | Permissions, nav visibility, home path |
| Chat | `frontend/components/chat/*` | Streaming UI, recommendation cards, tool traces, guardrail/workflow banners |
| UI kit | `frontend/components/ui/*` | Cards, KPIs, tables, badges, AskAgentBridge |

### 7.3 Interaction matrix (who calls whom)

| From | To | When |
|------|----|------|
| ChatPanel | `POST /api/chat` | User message |
| Workspace pages | `/api/borrowers*` | Directory, profile, payments, offers, score, what-if, submit-approval |
| Optimization | `/api/frontier`, `/api/frontier/jobs*` | Frontier view + async portfolio job |
| Approvals | `/api/workflows*` | List / KPI / PATCH status |
| Portfolio / Executive | `/api/portfolio/*`, `/api/executive/kpis` | Aggregates |
| Documents | `/api/documents/query` | RAG Q&A |
| Settings | `/api/settings/*` | Freshness, models, guardrails CRUD |
| Audit | `/api/audit*` | Recommendations, trails, conversation history |
| Orchestrator | ToolService, RAGService, GuardrailEngine, Gemini | Every chat turn |
| ToolService | Repositories, optimizer, model_scorer, GuardrailEngine | Tool execution |
| Seed / ModelScorer | `scoring.py` | Identical EV math |

---

## 8. Data Architecture

### 8.1 Conceptual model

```
dim_customer 1───1 fact_settlements_monthly
     │                    │
     │                    └── bridge_settlement_customer_account ── account
     ├── N fact_accounts_monthly
     ├── N fact_applications
     ├── N fact_payments / fact_activities
     ├── N fact_offer_grid_scores (9)
     ├── 1 fact_recommended_offers
     └── N fact_shap_explanations

Portfolio analytics ← fact_portfolio_kpis_monthly, fact_recommended_offers, settlements
Strategy            ← fact_efficient_frontier (+ live portfolio MILP)
Monitoring          ← fact_model_monitoring

Agent session       ← agent_conversations → messages / tool_calls / recommendations / audit_trail
Governance          ← workflow_tasks
Knowledge           ← document_chunks
Identity            ← app_users
```

### 8.2 Physical schema summary

Authoritative DDL: `backend/db/schema.sql` (also applied via Docker init). Lifespan migrations in `main.py` add/alter columns and tables for forward compatibility on existing volumes.

#### Dimensions

| Table | PK | Purpose |
|-------|----|---------|
| `dim_customer` | `customer_code` | Identity, segment, AML, compliance flags, vulnerability, OOD |
| `dim_region` | `region_id` | Geography reference |
| `dim_channel` | `channel_id` | Assignment channel |
| `dim_product` | `product_id` | Product / BU |
| `dim_portfolio` | `portfolio_id` | Portfolio grouping |

Customer flags that drive guardrails: `flag_deceased`, `flag_legal_entity`, `flag_under_law_protection`, `vulnerability_status`, `ood_flag`, plus corporate/campaign/legal flags used in seed/profile display.

#### Core facts

| Table | Purpose |
|-------|---------|
| `fact_settlements_monthly` | Settlement status, balances, arrears, channel, activity aggregates |
| `fact_accounts_monthly` | Per-account DPD, balances, product |
| `bridge_settlement_customer_account` | Settlement ↔ customer ↔ account |
| `fact_applications` | Application pipeline / terms / stages |
| `fact_payments` | Payment time series |
| `fact_activities` | Contact / collection activities |
| `fact_portfolio_kpis_monthly` | Monthly EV, collections, realization by segment |

#### Decision / AI facts

| Table | Purpose |
|-------|---------|
| `fact_offer_grid_scores` | 9 scored offers per customer |
| `fact_recommended_offers` | Seed-time “optimal” row (baseline); runtime may re-optimize via MILP |
| `fact_efficient_frontier` | Precomputed strategy points |
| `fact_model_monitoring` | Metric vs baseline + alert flag |
| `fact_shap_explanations` | Seeded feature attributions |

#### Agent, workflow, RAG, auth

| Table | Purpose |
|-------|---------|
| `agent_conversations` | Session header (`user_id` = email, role, domain) |
| `agent_messages` | User/assistant turns + intent + `metadata_json` |
| `agent_tool_calls` | Tool I/O JSONB + duration |
| `agent_recommendations` | Persisted recommendation snapshot + guardrail flag |
| `agent_audit_trail` | Event log (`actor_id`, entity, payload) |
| `workflow_tasks` | HITL / specialist tasks (`status`, `assigned_queue`, `risk_tier`, `decision_payload`, resolution fields) |
| `document_chunks` | RAG chunks + `vector(768)` |
| `app_users` | Login accounts |

### 8.3 Seed data contract

Produced by `backend/scripts/seed_db.py` (idempotent; `--force` rebuilds portfolio data):

| Entity | Scale |
|--------|-------|
| App users | 3 (`analyst@`, `manager@`, `admin@` @ `settlement.ai`) |
| Customers | 100 (`customer_code` 243445–243544) with legal names |
| Settlements | 100 (`settlement_code` 880012+) |
| Accounts | ~150 |
| Offer grid | 900 (9 × 100) |
| Password (all seeded users) | `Settlement1!` |

Sparse natural flags (deceased, corporate, vulnerable, OOD) are distributed for demo guardrail paths — see `content/mvp-mock-data-reference.md`.

### 8.4 Data movement patterns

| Flow | Direction | Mechanism |
|------|-----------|-----------|
| Bootstrap | Host → Postgres | `schema.sql` + `seed_db.py` |
| Policy knowledge | Filesystem → `document_chunks` | Lifespan / `POST /api/documents/ingest` |
| Runtime reads | UI/API → facts | Repository SQL |
| Runtime writes (agent) | Orchestrator → agent_* + workflow_tasks | ORM commit after SSE answer |
| Runtime writes (HITL) | Approvals UI → `workflow_tasks` | `PATCH /api/workflows/{id}` |
| Guardrail config | JSON file ↔ Settings API | `settings_store` load/save |
| Frontier jobs | In-memory `_jobs` dict | **Not durable** across process restart |

### 8.5 RAG embedding note

Embeddings are **deterministic SHA-256–derived pseudo-vectors** (768-d), not an external embedding model. Similarity is cosine over all chunks in Python. Acceptable for ~5 short policy docs; not production-scale semantic search.

---

## 9. Decision Engine

### 9.1 Probability scoring (simulated ModelScorer / T5)

`score_probabilities(customer_code, rr, installments, segment_factor)` returns deterministic PoAPP, PoA, PoF:

- Base depends on `customer_code % 12` and optional segment factor
- Higher RR tends to lower PoAPP / adjust PoF
- Higher installment count tends to lower PoA and raise PoF slightly
- Clamped to configured probability bands

`compute_ev` multiplies the three probabilities by settlement amount `balance × rr`.

On-demand API: `POST /api/borrowers/{code}/score` and chat intent `model_score`. Optional full-grid rescore uses the same formulas.

**This is not live ML inference.** SHAP rows are seeded, not computed from a trained explainer at runtime.

### 9.2 Single-borrower MILP (T2 OfferOptimiser)

`optimize_single_borrower` in `optimizer.py`:

1. Filter grid rows by RR bounds and optional `max_rr`, `min_p_fulfill`, `fixed_installments`
2. Binary variables: pick **exactly one** eligible offer
3. Objective: **maximize EV**
4. Solver: PuLP CBC
5. On infeasibility: raise `OptimizerError` (no silent greedy fallback)

Returned metadata includes `solver_status`, `mip_gap`, `optimizer: pulp_cbc`, `constraints_applied`.

### 9.3 Portfolio MILP

`optimize_portfolio`:

1. Per borrower, filter eligible offers
2. Exactly one offer assigned per included borrower
3. Maximize sum of EVs
4. Optional portfolio constraints from `guardrail_config.json` → `optimizer`:
   - `max_avg_rr`
   - `max_installment_share` (default 0.6) with `high_installment_threshold` (default 3)

Used by chat strategy (“optimize portfolio…”) and frontier constraint simulation.

### 9.4 Efficient frontier

- **Static points:** `fact_efficient_frontier` (seeded strategy names / EV / risk / constraint labels)
- **What-if:** live portfolio MILP under user-supplied `min_p_fulfill` / `max_rr`
- **Async jobs:** `POST /api/frontier/jobs` stores status in process memory (`jobs.py`), sleeps ~2s, runs `frontier_analysis`, poll via `GET /api/frontier/jobs/{id}`

---

## 10. Agent Orchestration

### 10.1 Design principle

The orchestrator is a **deterministic router**, not an LLM planner:

1. Classify intent with keyword/regex rules
2. Resolve borrower identity (name and/or code, with history)
3. Execute ToolService / RAG
4. Run guardrails / approval classification when recommending
5. Optionally polish prose with Gemini (system prompt forbids the LLM from inventing EV/probabilities)
6. Persist messages, tools, recommendations, audit events
7. Stream SSE events to the client

`langgraph` / LangChain are **not** used at runtime.

### 10.2 Intent catalog

| Intent | Example triggers | Primary tools |
|--------|------------------|---------------|
| `greeting` | hello, thanks | none (LLM/template) |
| `human_handoff` | speak to human, handoff | `create_handoff` |
| `policy_exception` | exception, grace period | RAG + `create_exception_request` |
| `model_score` | rescore, run PoA | `model_score` |
| `payment_history` | payment history, paid so far | `payment_history` |
| `debt_inquiry` | balance, outstanding | `borrower_lookup` |
| `restructuring` | restructure, monthly capacity | optimize (+ prompts) |
| `renegotiation` | more installments, change plan | optimize |
| `document` | policy, max recovery, vulnerability | `document_rag` |
| `strategy` | frontier, RR capped, optimize portfolio | `frontier_analysis` or portfolio `offer_optimization` |
| `portfolio` | KPI, segment, monitoring, PSI | `portfolio_analytics` / `monitoring` |
| `decision_explanation` | why, SHAP, driver | `explainability` |
| `recommendation` (default) | recommend, offer, settlement | lookup + MILP + explainability |

### 10.3 Borrower resolution

`_resolve_borrower`:

1. Extract customer code patterns and legal-name hints from the message
2. Search DB by name / code
3. Fall back to conversation history metadata / prior tool outputs
4. If missing → ask for **name and customer code** (no side effects)
5. If ambiguous → list `Legal Name (customer_code)` options

Display convention everywhere: **`Legal Name (customer_code)`**.

### 10.4 SSE event protocol

| Event `type` | Meaning |
|--------------|---------|
| `status` | Human-readable progress (“Understanding your question…”) |
| `tool_start` | Named tool beginning |
| `tool_done` | Tool output payload |
| `answer` | Final assistant markdown |
| `done` | Stream complete (includes conversation id / metadata as implemented) |

Frontend parser: `frontend/lib/api.ts` → `chatStream`.

### 10.5 Tool catalogue (ToolService)

| Tool method | Spec mapping | Behavior |
|-------------|--------------|----------|
| `borrower_lookup` | T1 | Profile + settlement + accounts + display_name |
| `offer_grid` | — | Raw 9-cell grid + recommended |
| `offer_optimization` | T2 | Single or portfolio MILP + guardrail/approval packaging |
| `portfolio_analytics` | T3 | KPI / segment aggregates |
| `frontier_analysis` | T4 | Frontier + constraint sim |
| `model_score` | T5 | Deterministic rescore |
| `explainability` | T6 | Seeded SHAP features |
| `monitoring` | T3 subset | Model health metrics |
| `payment_history` | — | Totals + recent payments |
| `installment_comparison` | — | EV deltas across installment counts |
| `create_handoff` / `create_exception_request` | HITL | Insert `workflow_tasks` |

### 10.6 Gemini contract

System prompt (`SYSTEM_PROMPT` in orchestrator):

- Conversational colleague tone
- Orchestrates tools; **never calculates EV or probabilities**
- Must cite exact tool numbers
- Must use `Legal Name (customer_code)`
- Probabilistic language only

If `GEMINI_API_KEY` is empty, `_fallback_*` templates are used.

---

## 11. Guardrails, Compliance, and HITL

### 11.1 Configuration source

`backend/content/guardrail_config.json` (also editable via Settings API for admins):

| Key | Default intent |
|-----|----------------|
| `rr_min` / `rr_max` | 0.20 / 0.80 |
| `flags.*` | Enable deceased / legal entity / law protection blocks; vulnerability / OOD warnings |
| `approval.ev_high_threshold` | 5000 → high risk approval |
| `approval.rr_bound_proximity` | 0.05 → near-bound approval |
| Queues | `manager_approval`, specialist queues for deceased / corporate / law protection |
| `optimizer.*` | Portfolio capacity knobs |

### 11.2 Evaluation (`GuardrailEngine.evaluate`)

| Condition | Status | Risk | Workflow |
|-----------|--------|------|----------|
| Borrower not found | blocked | — | none |
| `flag_deceased = 1` | blocked | high | `deceased_escalation` |
| `flag_legal_entity = 1` | blocked | high | `corporate_collections` |
| `flag_under_law_protection = 1` | blocked | high | `law_protection_review` |
| RR outside bounds | blocked | high | compliance/manager queue |
| `vulnerability_status ≠ None` | warning | high | pending manager approval |
| `ood_flag` | warning | high | pending manager approval |
| Else | passed | low | none |

### 11.3 Decision classification (`classify_decision`)

Applied after an offer is selected:

- Blocked guard → specialist explanation; `requires_approval=true`
- Warning → force approval, high tier
- RR within proximity of bounds → medium/high + approval
- EV ≥ threshold → high + approval
- Emits `customer_explanation` text for UI/chat

### 11.4 Workflow task lifecycle

| Status | Meaning |
|--------|---------|
| `open` | Specialist escalation created by hard block / handoff |
| `pending_approval` | Recommendation awaiting manager decision |
| `approved` / `rejected` / `escalated` | Terminal manager actions |
| (ack/resolve variants as exposed by UI) | Analyst/manager operational closure |

**Actors:** Managers and Admins hold `workflows_approve`. Analysts can see limited workflow interaction depending on route checks; approval mutations are restricted server-side.

**UI:** `/approvals` (primary), legacy alias `/workflows`.

**Audit:** Task resolution stores `resolution_note`, `resolved_by`; agent path also writes `agent_audit_trail` / recommendations.

---

## 12. End-to-End Business Workflows

### 12.1 Authentication

```
User → /login → POST /api/auth/login
     ← JWT (sub, email, role, full_name)
Frontend stores token (localStorage + cookie)
Subsequent API calls send Bearer token
GET /api/auth/me hydrates session
Middleware blocks anonymous page access
```

Home path after login: analyst → `/workspace`; manager → `/approvals`; admin → `/settings`.

### 12.2 Conversational settlement recommendation

```
Analyst opens Assistant / ChatPanel
  → "Recommend a settlement for James Smith 243445"
POST /api/chat (SSE)
  → classify intent = recommendation
  → resolve borrower James Smith (243445)
  → borrower_lookup
  → offer_optimization (single MILP)
  → GuardrailEngine.evaluate + classify_decision
  → optional explainability
  → Gemini polish
  → persist messages / tools / recommendation / audit
  → SSE: status → tool_* → answer → done
UI renders RecommendationCard + GuardrailPanel + WorkflowBanner if needed
If requires_approval → workflow_tasks.pending_approval created
```

### 12.3 Workspace-driven case work

```
Analyst → /workspace → GET /api/borrowers
Open /workspace/{code}
  → profile, payments, offers, SHAP
Actions:
  • POST .../score — rescore
  • POST .../what-if — constrained MILP (422 if blocked)
  • POST .../submit-approval — explicit HITL submission
Ask-Agent bridge can fire CustomEvent to ChatPanel with prefilled question
```

### 12.4 Manager approval

```
Manager → /approvals → GET /api/workflows
Review decision_payload / reason / risk_tier
PATCH /api/workflows/{task_id} { status, resolution_note }
  → approved | rejected | escalated
KPIs via GET /api/workflows/kpis (approval rate, SLA breaches, avg resolution)
```

### 12.5 Portfolio strategy / frontier job

```
Manager/Admin → /optimization
GET /api/frontier (static + sim params)
POST /api/frontier/jobs?max_rr=&min_p_fulfill=  (strategy_run)
Poll GET /api/frontier/jobs/{id} until done|error
Chat equivalent: "Optimize portfolio with RR capped at 50%"
```

Analysts have `strategy_read` but **not** `strategy_run` — they can view frontier, not enqueue portfolio jobs.

### 12.6 Document Q&A

```
Any permitted role → /documents
POST /api/documents/query { question }
RAGService embeds query (hash), top-3 chunks
UI shows context/sources (LLM synthesis not applied on this page)
Chat document intent: same RAG + Gemini polish
```

### 12.7 Recommended demo script (QA)

1. Login as `analyst@settlement.ai` / `Settlement1!`
2. Workspace → open a borrower → review grid + payments
3. Chat: `Recommend a settlement for <Legal Name> <code>`
4. Chat: `Payment history for <Legal Name> (<code>)`
5. Chat: `Rescore borrower <Legal Name> <code>`
6. Documents: `What is the max recovery rate?` → expect 20–80%
7. Login as `manager@settlement.ai` → Approvals → Approve/Reject
8. Portfolio + Executive dashboards
9. Optimization → run frontier job (manager/admin)

---

## 13. Security, Identity, and Authorization

### 13.1 Authentication mechanism

| Aspect | Implementation |
|--------|----------------|
| Credentials | Email + password against `app_users` |
| Password storage | bcrypt via passlib |
| Token | JWT HS256; claims `sub`, `email`, `role`, optional `full_name` |
| Lifetime | `JWT_EXPIRE_MINUTES` (default 480) |
| Transport | `Authorization: Bearer` |
| Logout | Client discards token; `POST /api/auth/logout` is effectively a no-op server-side |

### 13.2 Permission matrix

| Permission | Analyst | Manager | Admin |
|------------|:-------:|:-------:|:-----:|
| `chat` | ✓ | ✓ | ✓ |
| `borrower` | ✓ | ✓ | ✓ |
| `strategy_read` | ✓ | ✓ | ✓ |
| `strategy_run` | | ✓ | ✓ |
| `documents_read` | ✓ | ✓ | ✓ |
| `portfolio_read` | | ✓ | ✓ |
| `executive_read` | | ✓ | ✓ |
| `monitoring_read` | | ✓ | ✓ |
| `workflows` / `workflows_approve` | | ✓ | ✓ |
| `audit_read` / `audit_export` | | ✓ | ✓ |
| `settings_read` / `settings_write` | | | ✓ |

Enforcement: `require_permission(role, …)` on routes; frontend mirrors for UX only.

### 13.3 Defense in depth

1. Next middleware (cookie presence)
2. ClientLayout path → permission redirect
3. Sidebar link filtering
4. Backend JWT validation + permission checks

### 13.4 Security posture (MVP honesty)

| Topic | Status |
|-------|--------|
| Demo DB credentials in Compose | Hardcoded `settlement`/`settlement` |
| Default JWT secret | Dev default in Compose / `.env.example` |
| Refresh tokens / SSO / MFA | Not implemented |
| `/api/dashboard` | Aggregated endpoint; confirm permission posture when hardening |
| Rate limiting / WAF | Not implemented |
| Secrets manager | Not implemented |

Suitable for **local demo / controlled PoC**, not production exposure without hardening.

---

## 14. API Surface

OpenAPI UI: `http://localhost:8000/docs`. All protected routes need Bearer JWT unless noted.

### 14.1 Health & auth

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/health` | none | Liveness |
| POST | `/api/auth/login` | none | Issue JWT |
| GET | `/api/auth/me` | authenticated | Current user |
| POST | `/api/auth/logout` | none | Client logout helper |

### 14.2 Agent & documents

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| POST | `/api/chat` | `chat` | SSE chat |
| POST | `/api/chat/sync` | `chat` | Synchronous chat |
| POST | `/api/documents/query` | `documents_read` | RAG Q&A |
| POST | `/api/documents/ingest` | `settings_write` | Re-ingest policies |

### 14.3 Borrowers

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/borrowers` | `borrower` | Directory |
| GET | `/api/borrowers/search` | `borrower` | Search |
| GET | `/api/borrowers/{code}` | `borrower` | Profile |
| GET | `/api/borrowers/{code}/payments` | `borrower` | Payments |
| GET | `/api/borrowers/{code}/offers` | `borrower` | Offer grid |
| GET | `/api/borrowers/{code}/explain` | `borrower` | SHAP |
| POST | `/api/borrowers/{code}/what-if` | `borrower` | Constrained MILP |
| POST | `/api/borrowers/{code}/score` | `borrower` | ModelScorer |
| POST | `/api/borrowers/{code}/submit-approval` | `borrower` | Create approval task |

### 14.4 Portfolio, executive, strategy, jobs

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/dashboard` | (see code) | Aggregated dashboard |
| GET | `/api/portfolio/kpis` | `portfolio_read` | KPIs |
| GET | `/api/portfolio/segments` | `portfolio_read` | Segments |
| GET | `/api/portfolio/timeseries` | `portfolio_read` | Time series |
| GET | `/api/portfolio/export` | `portfolio_read` | CSV export |
| GET | `/api/executive/kpis` | `executive_read` | Strategic KPIs |
| GET | `/api/frontier` | `strategy_read` | Frontier + sim |
| POST | `/api/frontier/jobs` | `strategy_run` | Async MILP job |
| GET | `/api/frontier/jobs/{id}` | `strategy_read` | Job poll |
| GET | `/api/monitoring` | `monitoring_read` | Model health |

### 14.5 Workflows, audit, settings

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/workflows` | `workflows` | Task list |
| GET | `/api/workflows/kpis` | `workflows` | Approval KPIs |
| PATCH | `/api/workflows/{id}` | `workflows` (+ approve role for decisions) | Update task |
| GET | `/api/audit` | `audit_read` | Combined audit |
| GET | `/api/audit/recommendations` | `audit_read` | Recommendations |
| GET | `/api/audit/export` | `audit_export` | Export |
| GET | `/api/audit/conversations` | `chat` | Conversation index |
| GET | `/api/audit/conversations/{id}/messages` | `chat` | Transcript |
| GET | `/api/settings/freshness` | `chat` | Data vintage |
| GET | `/api/settings/models` | `settings_read` | Model versions |
| GET/PUT | `/api/settings/guardrails` | `settings_read` / `settings_write` | Guardrail config |

---

## 15. Frontend Information Architecture

### 15.1 Six primary views

| View | Route | Roles | Backend dependencies |
|------|-------|-------|----------------------|
| Collection Workspace | `/workspace`, `/workspace/[id]` | All with `borrower` | Borrowers APIs |
| Settlement Optimization | `/optimization` | `strategy_read` (+ run for jobs) | Frontier / jobs |
| Portfolio Monitoring | `/portfolio` | Manager, Admin | Portfolio APIs |
| Approvals & Exceptions | `/approvals` | Manager, Admin | Workflows APIs |
| Executive Dashboard | `/executive` | Manager, Admin | Executive KPIs |
| AI Assistant | `/assistant` | All with `chat` | Chat SSE |

### 15.2 Secondary views

Documents (`/documents`), Model Health (`/monitoring`), Audit (`/audit`), Settings (`/settings`).

### 15.3 Legacy aliases

| Alias | Maps to |
|-------|---------|
| `/borrowers`, `/borrowers/[id]` | Workspace |
| `/chat` | Assistant |
| `/strategy` | Optimization |
| `/workflows` | Approvals |

### 15.4 Chat as spine

`ClientLayout` mounts a persistent `ChatPanel`. Pages can dispatch `ask-agent` window events (via `AskAgentBridge`) so table/KPI contexts jump into chat with a prefilled prompt — keeping conversational decisioning adjacent to structured views.

### 15.5 State management

No global data store. Auth is Context; each page fetches with `cache: "no-store"`. Chat holds local message state and conversation id.

---

## 16. Configuration and Secrets

### 16.1 Environment variables

| Variable | Consumer | Default / notes |
|----------|----------|-----------------|
| `GEMINI_API_KEY` | Backend | Empty → template replies |
| `GEMINI_MODEL` | Backend | `gemini-3-flash-preview` |
| `DATABASE_URL` | Backend / seed | asyncpg URL |
| `CORS_ORIGINS` | Backend | `http://localhost:3000` |
| `JWT_SECRET` | Backend | Dev default if unset |
| `JWT_EXPIRE_MINUTES` | Backend | 480 |
| `NEXT_PUBLIC_API_URL` | Frontend | `http://localhost:8000` |

Template: `.env.example`. Compose injects Gemini/JWT from host `.env`.

### 16.2 Runtime config file

`backend/content/guardrail_config.json` — RR envelope, approval thresholds, optimizer capacity. Editable through Admin Settings when `settings_write` is granted.

### 16.3 Policy content

`content/docs/*.md` mounted into the backend container:

- `recovery-rate-policy.md`
- `deceased-borrower-policy.md`
- `corporate-collections-policy.md`
- `vulnerability-policy.md`
- `poa-model-card.md`

---

## 17. Operations Runbook

### 17.1 First-time bring-up

```bash
cp .env.example .env
# Set GEMINI_API_KEY (optional but recommended)
docker compose up --build
```

- Frontend: http://localhost:3000  
- API: http://localhost:8000  
- OpenAPI: http://localhost:8000/docs  

### 17.2 Common operations

| Task | Command / action |
|------|------------------|
| Clean rebuild after bad seed | `docker compose down -v && docker compose up --build` |
| Force reseed | `docker compose exec backend python scripts/seed_db.py --force` |
| Re-ingest RAG docs | Restart backend or `POST /api/documents/ingest` (admin) |
| Change guardrails | Admin Settings UI or edit JSON + PUT API |
| Validate EV math | `python backend/scripts/validate_hero.py` |
| View API contract | `/docs` |

### 17.3 Schema change procedure (MVP)

1. Update `backend/db/schema.sql` and ORM entities.
2. For existing volumes, either add a lifespan `ALTER`/`CREATE IF NOT EXISTS` in `main.py` **or** reset volume (`down -v`).
3. There is **no Alembic** migration chain — treat schema evolution carefully.

### 17.4 Backup / restore (demo)

Postgres data lives in Docker volume `postgres_data`. Standard `docker run --volumes-from` / `pg_dump` practices apply; no project-specific backup scripts ship with the MVP.

### 17.5 Failure modes

| Symptom | Likely cause | Mitigation |
|---------|--------------|------------|
| Seed errors on restart | Partial previous seed | `down -v` then up |
| Chat generic answers | Missing Gemini key | Set key or accept templates |
| Frontier job lost | Backend reload | Jobs are in-memory only; re-submit |
| Empty documents answers | Ingest failed / empty docs mount | Check volume mount + ingest logs |
| 403 on UI | Role lacks permission | Use correct seeded account |

---

## 18. Observability, Performance, and Limits

### 18.1 What exists

- Uvicorn access/error logs
- Tool `duration_ms` stored on `agent_tool_calls`
- SSE progress events for perceived latency
- Model monitoring **data** in DB (demo metrics), not an APM stack
- Data vintage strip in UI (`/api/settings/freshness`)

### 18.2 What does not exist

Structured logging standard, distributed tracing, Prometheus metrics, centralized error tracking, rate limits, circuit breakers.

### 18.3 Performance characteristics

| Area | Behavior |
|------|----------|
| DB | Async SQLAlchemy; indexes on offer grid, recommended, SHAP, legal_name |
| MILP | Small grids (9 cells / ~100 borrowers) — CBC is fine for demo |
| RAG | Full chunk scan in Python — OK for tiny corpora only |
| Gemini | Adds network latency per polished reply |
| Frontend in Compose | Dev server — not production-optimized |
| Frontier jobs | Artificial 2s delay + in-memory store |

---

## 19. Testing and Quality Assurance

### 19.1 Automated tests present

| Asset | Scope |
|-------|-------|
| `backend/scripts/validate_hero.py` | Standalone EV formula check |

### 19.2 Gaps

No pytest suite, no frontend unit/E2E framework, no CI workflows in-repo.

### 19.3 Manual QA checklist (minimum)

- [ ] Login all three roles; verify home paths and nav filtering
- [ ] Workspace search/filter/profile/offers/payments
- [ ] Chat recommendation with name+code; verify SSE tool trace
- [ ] Guardrail: deceased / vulnerable / OOD paths create correct queues/statuses
- [ ] Manager approve/reject with resolution note
- [ ] Portfolio + executive KPI load
- [ ] Frontier job complete for manager; 403 for analyst `strategy_run`
- [ ] Document Q&A returns RR policy bounds
- [ ] Audit shows recommendation after chat
- [ ] Admin can read/update guardrails

---

## 20. As-Built vs Target Architecture

| Capability | As-built MVP | Target (pitch / spec) |
|------------|--------------|------------------------|
| Decision UI + chat | ✓ | ✓ |
| EV / probability chain | Deterministic shared formulas | Live trained models (`.pkl`) |
| Offer optimiser | Real PuLP CBC MILP | Same + production capacity models |
| Explainability | Seeded SHAP rows | Live explainers |
| Guardrails + HITL | ✓ deterministic | ✓ + enterprise case management |
| RAG | Hash pseudo-embeddings | Real embeddings + policy CMS |
| Auth | Local JWT users | SSO / MFA / enterprise IdP |
| Data | Synthetic seed | Parquet / CRM / warehouse ETL |
| Messaging | None | Kafka / MQ |
| Orchestration framework | Custom Python | Spec mentions LangGraph (unused dep today) |
| Deployment | Docker Compose dev | K8s, TLS, secrets, HA |

Track implementation progress against `Settlement_Portfolio_Intelligence_Agent.md`.

---

## 21. Glossary

| Term | Definition |
|------|------------|
| **RR** | Recovery rate — settlement amount as fraction of balance |
| **EV** | Expected Value — PoAPP × PoA × PoF × (Balance × RR) |
| **PoAPP / PoA / PoF** | Probabilities of application, acceptance, fulfillment |
| **Offer grid** | Discrete RR × installment combinations scored per borrower |
| **MILP** | Mixed-Integer Linear Program (binary offer assignment) |
| **HITL** | Human-in-the-loop approval / specialist review |
| **OOD** | Out-of-distribution flag — model confidence / population shift signal |
| **RAG** | Retrieval-Augmented Generation over policy markdown |
| **SSE** | Server-Sent Events streaming for chat |
| **T1–T6** | Spec tool identifiers (Lookup, Optimiser, Monitor, Frontier, Scorer, Explainer) |

---

## 22. Appendix — Repository Map

```
MVP/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
├── Settlement_Portfolio_Intelligence_Agent.md      # Spec checklist
├── Settlement_Portfolio_AI_Project_Checklist.md
├── CURSOR_IMPLEMENTATION_GUIDE_Settlement_Portfolio_AI.md
├── settlment_portfolio.md                          # Pitch / target architecture
├── Quant_data_layout_08062026.xlsx                 # Field layout (no data rows)
├── docs/
│   ├── OPERATIONAL_ARCHITECTURE_AND_SYSTEM_DOCUMENTATION.md  # this document
│   └── SYSTEM_DOCUMENTATION.md                     # shorter as-built companion
├── content/
│   ├── docs/                                       # RAG policy markdown
│   ├── decision-intelligence-agent-specification.md
│   ├── database-schema.md
│   ├── Spec.md
│   ├── project-report.md
│   └── mvp-mock-data-reference.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── content/guardrail_config.json
│   ├── db/schema.sql
│   ├── scripts/seed_db.py
│   ├── scripts/validate_hero.py
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── agents/orchestrator.py
│       ├── api/routes/
│       ├── auth/
│       ├── guardrails/engine.py
│       ├── models/entities.py
│       ├── rag/service.py
│       ├── repositories/borrower.py
│       ├── services/          # scoring, model_scorer, optimizer, settings_store
│       └── tools/service.py
└── frontend/
    ├── Dockerfile
    ├── middleware.ts
    ├── app/                   # App Router pages
    ├── components/            # chat, ui, AuthProvider, Sidebar, ClientLayout
    └── lib/                   # api, roles, format, chartTheme
```

---

*End of document. For day-to-day setup commands, prefer `README.md`. For feature completion status vs specification, prefer `Settlement_Portfolio_Intelligence_Agent.md`.*
