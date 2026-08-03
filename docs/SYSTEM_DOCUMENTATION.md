# Settlement Portfolio AI Agent — System Documentation

This document describes the **Settlement Portfolio AI Agent MVP** as implemented in this repository. It is based strictly on the current code, configuration, and deployment setup — not on planned or aspirational features from the business specification alone.

---

## 1. What the Project Does and Why It Exists

### Purpose

The project is a **Decision Intelligence Layer** for debt settlement portfolios. Collections analysts, managers, and executives can ask questions in plain English and receive answers backed by precomputed model scores, portfolio analytics, compliance guardrails, and policy documents.

The business goal (documented in `content/decision-intelligence-agent-specification.md`) is to replace fragmented analyst workflows — predictive models, optimization notebooks, and batch scripts — with a single conversational interface: *"Ask a question in plain English and receive a model-backed answer instantly."*

### What Is Actually Built

The MVP delivers:

- A **Next.js dashboard** with portfolio KPIs, borrower profiles, efficient frontier exploration, model monitoring, workflow inbox (approve/reject/escalate), audit log, document Q&A, and a streaming AI chat.
- A **FastAPI backend** with an agent orchestrator (Google Gemini), expanded keyword intents, **name + customer-code** borrower resolution, compliance guardrails with risk-tier approval routing, and audit persistence.
- A **PostgreSQL + pgvector** database seeded with **100** mock borrowers, offer grids, SHAP explanations, frontier data, and policy documents for RAG.
- **PuLP CBC MILP** for single-borrower and portfolio offer assignment over the seeded offer grid.
- A **simulated ModelScorer (T5)** that recomputes PoAPP/PoA/PoF/EV deterministically via shared scoring math.
- **Docker Compose** orchestration for local/demo deployment.

The system does **not** run live `.pkl` model inference or ingest production parquet/CRM feeds. Offer grids and SHAP values are **pre-seeded**; on-demand scoring reuses the same deterministic formulas as the seeder (`backend/app/services/scoring.py`). Optimization is a **real MILP solver** over that grid — not live trained models.

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         User (Browser)                                   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP (port 3000)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Frontend — Next.js 14 (App Router, React 18, Tailwind, Recharts)       │
│  • Dashboard, Chat, Portfolio, Borrowers, Documents, Workflows, etc.   │
│  • JWT session; role from login (RBAC on nav + API)                    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ REST + SSE (NEXT_PUBLIC_API_URL → :8000)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Backend — FastAPI (Python 3.12, Uvicorn)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ API Routes   │→ │ Orchestrator │→ │ ToolService  │→ │ Repositories │ │
│  └──────────────┘  │ (Gemini LLM) │  └──────┬───────┘  └──────────────┘ │
│                    └──────┬───────┘         │                           │
│                           │         ┌───────┴────────┐                  │
│                    ┌──────▼───────┐ │ PuLP MILP      │ ┌──────────────┐ │
│                    │ RAGService   │ │ ModelScorer    │ │ Guardrail +  │ │
│                    │ (pgvector)   │ │ scoring.py     │ │ Approval     │ │
│                    └──────────────┘ └────────────────┘ └──────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ asyncpg (SQLAlchemy 2.0)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16 + pgvector (port 5432)                                    │
│  • Dimension/fact tables (borrowers, settlements, offer grids)         │
│  • Agent audit tables (conversations, messages, tool calls, workflows)   │
│  • document_chunks (768-dim embeddings)                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14.2, TypeScript, Tailwind CSS, Recharts, react-markdown |
| Backend | FastAPI 0.115, Uvicorn, Pydantic Settings |
| Database | PostgreSQL 16, pgvector extension |
| ORM | SQLAlchemy 2.0 (async via asyncpg) |
| LLM | Google Gemini (`google-genai`, model default: `gemini-3-flash-preview`) |
| Optimizer | PuLP 2.9 + CBC (single-borrower and portfolio MILP) |
| Containerization | Docker Compose (3 services: postgres, backend, frontend) |

---

## 3. How the Parts Connect

### Request Flow (Chat Example)

1. User opens Agent chat and sends: *"Recommend a settlement for Jane Smith 243445"* (name and/or code).
2. Frontend calls `POST /api/chat` with `{ message, conversation_id }` and `Authorization: Bearer` via SSE (`frontend/lib/api.ts` → `chatStream`).
3. Backend resolves role from the JWT; `AgentOrchestrator` classifies intent and resolves borrower via **`_resolve_borrower`** (legal name search + customer code; disambiguates multi-matches).
4. Tools run as needed, for example:
   - `borrower_lookup` — profile from `dim_customer`, settlements, accounts
   - `offer_optimization` — **PuLP MILP** over `fact_offer_grid_scores` (with guardrail + approval classification)
   - `explainability` — SHAP features from `fact_shap_explanations` (if user asks "why")
   - `model_score` — simulated on-demand PoAPP/PoA/PoF/EV
5. `GuardrailEngine` evaluates compliance flags and risk tier; may create `pending_approval` workflow tasks.
6. Gemini polishes the draft answer (or template fallback if no API key). Replies cite **`Legal Name (customer_code)`**.
7. Orchestrator persists `agent_messages`, `agent_tool_calls`, `agent_recommendations`, `agent_audit_trail` (actor = user email).
8. SSE events stream to the UI: `status` → `tool_start` → `tool_done` → `answer` → `done`.
9. `AssistantMessage` renders markdown, recommendation card (solver status, risk tier, needs-approval), guardrail panel, workflow banner, tool trace.

### Request Flow (Borrower directory)

1. Authenticated user opens `/borrowers`.
2. Frontend calls `GET /api/borrowers` with Bearer token.
3. Backend returns all seeded customers (filters optional); UI shows a table with search/segment/status filters.
4. Selecting a row navigates to `/borrowers/{id}` for the full profile.

### Startup Flow (Docker)

1. Postgres starts; `backend/db/schema.sql` runs on first init via Docker entrypoint.
2. Backend waits for Postgres healthcheck, runs `python scripts/seed_db.py` (idempotent), then `uvicorn app.main:app`.
3. On FastAPI lifespan startup: inline migration for `agent_messages`, then `RAGService.ingest_documents()` loads `content/docs/*.md` into `document_chunks`.

---

## 4. Component Responsibilities

### Frontend (`frontend/`)

| Area | Responsibility |
|------|----------------|
| `app/` | App Router pages — one route per major feature |
| `components/chat/` | Rich chat UI (markdown, guardrails, recommendations, tool traces) |
| `components/ui/` | Reusable primitives (cards, tables, badges, alerts) |
| `components/Sidebar.tsx` | Navigation with role-based link visibility; signed-in user + sign out |
| `components/AuthProvider.tsx` | JWT session, user identity, role derived from login |
| `app/login/page.tsx` | Branded sign-in |
| `middleware.ts` | Redirects unauthenticated users to `/login` |
| `lib/api.ts` | Central HTTP client; Bearer token; SSE chat streaming |
| `lib/format.ts`, `lib/chartTheme.ts` | Formatting and chart styling helpers |

**Routes:**

| Route | Purpose |
|-------|---------|
| `/login` | Email/password sign-in |
| `/` | Redirects to role home (or login) |
| `/chat` | AI Command Center (streaming chat) |
| `/portfolio` | Portfolio KPIs and segment breakdown |
| `/borrowers` | Full borrower directory (all seeded customers) |
| `/borrowers/[id]` | Borrower profile, offer grid, SHAP explainability |
| `/documents` | Policy document Q&A (RAG) |
| `/workflows` | Escalation task inbox |
| `/monitoring` | Model health metrics |
| `/strategy` | Efficient frontier explorer |
| `/audit` | Recommendation audit trail |
| `/settings` | Admin guardrails and model settings |

### Backend (`backend/`)

| Module | Responsibility |
|--------|----------------|
| `app/main.py` | FastAPI app, CORS, lifespan, router registration, `/health` |
| `app/config.py` | Environment settings (`DATABASE_URL`, `GEMINI_API_KEY`, etc.) |
| `app/database.py` | Async SQLAlchemy engine and `get_db` dependency |
| `app/agents/orchestrator.py` | Intent classification, name+code borrower resolve, tool routing, Gemini polish, audit persistence |
| `app/tools/service.py` | Tool facade (lookup, MILP optimize, score, payments, portfolio, frontier, monitoring, explainability, handoff) |
| `app/services/scoring.py` | Shared PoAPP/PoA/PoF + EV math (seed + runtime) |
| `app/services/model_scorer.py` | Simulated on-demand ModelScorer (T5) |
| `app/services/optimizer.py` | PuLP CBC single-borrower and portfolio MILP |
| `app/repositories/borrower.py` | Data access for borrowers, portfolio, frontier, monitoring |
| `app/guardrails/engine.py` | Compliance checks, risk tiers, approval routing, workflow task creation |
| `app/rag/service.py` | Document ingestion and similarity search |
| `app/auth/rbac.py` | JWT-backed role dependency and permission checks |
| `app/auth/security.py` | Password hashing and JWT create/decode |
| `app/api/routes/auth.py` | `/api/auth/login`, `/me`, `/logout` |
| `app/api/routes/` | REST endpoints grouped by domain |
| `app/models/entities.py` | SQLAlchemy ORM models (includes `app_users`, extended `workflow_tasks`) |
| `content/guardrail_config.json` | RR bounds, approval thresholds, optimizer capacity knobs |
| `scripts/seed_db.py` | Idempotent mock data + seed app users (imports shared scoring) |
| `db/schema.sql` | Full PostgreSQL schema |

### Content (`content/`)

| Path | Role |
|------|------|
| `content/docs/*.md` | Policy documents ingested for RAG (recovery rate, deceased, vulnerability, corporate, model card) |
| `content/decision-intelligence-agent-specification.md` | Business/architecture specification (reference, not runtime) |
| `content/mvp-mock-data-reference.md` | Mock data reference for demo scenarios |

---

## 5. Data Model and Data Movement

### Schema Overview (`backend/db/schema.sql`)

**Dimension tables:** `dim_customer`, `dim_region`, `dim_channel`, `dim_product`, `dim_portfolio`

**Fact tables (portfolio/borrower data):**
- `fact_settlements_monthly` — settlement balances, status, payments
- `fact_accounts`, `fact_applications`, `fact_payments`, `fact_activities`
- `fact_offer_grid_scores` — 9 combos per borrower (3 RR × 3 installment counts)
- `fact_recommended_offers` — precomputed optimal offers
- `fact_efficient_frontier` — portfolio strategy points
- `fact_model_monitoring` — model metrics and alert flags
- `fact_shap_explanations` — feature-level explainability

**Agent/audit tables:**
- `agent_conversations`, `agent_messages`, `agent_tool_calls`
- `agent_recommendations`, `agent_audit_trail`
- `workflow_tasks` — escalations / approvals (`risk_tier`, `decision_payload`, `resolution_note`, `resolved_by`, statuses including `pending_approval` / `approved` / `rejected` / `escalated`)

**RAG:** `document_chunks` with `vector(768)` embeddings

**Auth:** `app_users` — email, hashed password, role (`analyst` | `manager` | `stakeholder` | `compliance` | `admin`)

### Mock Data (`backend/scripts/seed_db.py`)

| Entity | Count | Notes |
|--------|-------|-------|
| App users | 5 | One per role; password `Settlement1!` |
| Customers | 100 | Codes 243445–243544 with legal names |
| Settlements | 100 | Codes 880012+ |
| Offer grid | 900 | 9 combos per borrower |

Seeding is **idempotent** — safe to re-run on container restart. App users are upserted even when portfolio data is already present.

### Optimization Logic (Implemented)

**Single borrower** — `optimize_single_borrower` in `backend/app/services/optimizer.py` (via `BorrowerRepository.optimize_offer` / `ToolService.offer_optimization`):

1. Loads all `fact_offer_grid_scores` rows for the customer.
2. Filters by guardrail RR bounds and optional `max_rr`, `min_p_fulfill`, `fixed_installments`.
3. Solves a **PuLP CBC MILP**: binary pick exactly one offer; maximize EV.
4. Returns chosen offer plus `solver_status`, `mip_gap`, `optimizer`, `constraints_applied`.
5. On solver infeasibility/failure, returns a clear error (no silent greedy fallback).

**Portfolio** — `optimize_portfolio` (chat strategy / frontier constraint sim):

1. Loads offer grids for N borrowers.
2. Binary assign exactly one feasible offer per borrower; maximize total EV.
3. Optional constraints from `guardrail_config.json` → `optimizer`: `max_avg_rr`, `max_installment_share`.
4. `FrontierRepository.simulate_constraint` uses this MILP (not per-customer greedy max).

**ModelScorer (T5, simulated)** — `backend/app/services/model_scorer.py`:

- Recomputes PoAPP/PoA/PoF/EV with the same formulas as the seeder.
- Exposed as `ToolService.model_score` and `POST /api/borrowers/{id}/score`.

Guardrails + approval classification run around recommendations (`GuardrailEngine.classify_decision`).

### RAG Data Flow

1. On startup, `RAGService.ingest_documents()` deletes existing chunks and re-reads `content/docs/*.md`.
2. Text is split into ~400-character paragraph chunks.
3. Each chunk gets a **deterministic hash-based pseudo-embedding** (768 dimensions) — no external embedding API.
4. Queries embed the question the same way, score all chunks by cosine similarity in Python, return top 3.
5. `/api/documents/query` returns `{ question, sources, context }` — the orchestrator or documents page uses this context; Gemini is not used for document answers on the documents page (context is returned directly).

---

## 6. API Reference (Implemented Endpoints)

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"status": "ok"}` |

### Agent & Operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Streaming chat (SSE) |
| POST | `/api/chat/sync` | Synchronous chat (used by API, not frontend pages) |
| POST | `/api/documents/query` | RAG document Q&A |
| POST | `/api/documents/ingest` | Re-ingest policy documents |
| GET | `/api/workflows` | List workflow tasks (`status`, `queue` filters) |
| PATCH | `/api/workflows/{task_id}` | Update status + optional `resolution_note` (approve/reject/escalate restricted to manager/compliance/admin) |
| GET | `/api/audit/recommendations` | Last 50 agent recommendations |

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard` | Aggregated dashboard payload |

### Borrowers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/borrowers/{customer_code}` | Borrower profile |
| GET | `/api/borrowers/{customer_code}/offers` | Offer grid + recommended offer |
| POST | `/api/borrowers/{customer_code}/what-if` | Constrained optimization (422 if blocked) |
| GET | `/api/borrowers/{customer_code}/explain` | SHAP explainability (`model` query param) |
| POST | `/api/borrowers/{customer_code}/score` | Simulated on-demand ModelScorer (optional grid rescore) |

### Portfolio & Strategy

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/kpis` | Portfolio KPIs |
| GET | `/api/portfolio/segments` | Segment breakdown |
| GET | `/api/frontier` | Efficient frontier + constraint simulation |
| GET | `/api/monitoring` | Model monitoring metrics and alerts |

OpenAPI docs are auto-generated at `http://localhost:8000/docs`.

---

## 7. Agent Orchestration

### Intent Classification

`AgentOrchestrator` uses **keyword/regex rules** (not an LLM) to classify intents. Borrower-scoped flows resolve identity via **legal name and/or customer code** (`_resolve_borrower`).

| Intent | Triggers | Tools Used |
|--------|----------|------------|
| `greeting` | hello, thanks, etc. | Gemini/template only |
| `document` | policy, regulation, vulnerability | `document_rag` |
| `portfolio` | KPIs, segments, monitoring | `portfolio_analytics` or `monitoring` |
| `strategy` | frontier, constraints, what-if, optimize portfolio | `frontier_analysis` or portfolio `offer_optimization` |
| `debt_inquiry` | balance, outstanding | `borrower_lookup` |
| `payment_history` | payment history, paid so far | `payment_history` |
| `restructuring` / `renegotiation` | restructure, more installments | MILP optimize + optional slot prompts |
| `recommendation` | recommend, offer, settlement (default) | lookup + MILP + explainability |
| `decision_explanation` | why, explain, shap | `explainability` |
| `policy_exception` | exception, grace period | RAG + `exception_request` workflow |
| `human_handoff` | speak to human, handoff | `human_handoff` workflow |
| `model_score` | rescore, model score | `model_score` |

Missing identity → ask for **name and customer code** (no tool side-effects). Ambiguous names → list `Name (code)` options.

### Tools (`ToolService`)

| Tool | Data Source | Output |
|------|-------------|--------|
| `borrower_lookup` | dim/fact tables | Profile, settlement, accounts, `display_name` |
| `payment_history` | `fact_payments` | Totals + recent payments |
| `offer_optimization` | offer grid + **PuLP MILP** + guardrails | Optimal offer / portfolio assignment or block |
| `model_score` | balance + `scoring.py` | Simulated PoAPP/PoA/PoF/EV |
| `portfolio_analytics` | Aggregations on recommended offers/settlements | KPIs + segments |
| `frontier_analysis` | frontier table + portfolio MILP sim | Frontier points + constraint simulation |
| `monitoring` | `fact_model_monitoring` | Metrics + alerts |
| `explainability` | `fact_shap_explanations` | Top positive/negative features |
| `installment_comparison` | Offer grid cross-join | EV deltas when switching installment counts |
| `human_handoff` / exception | `workflow_tasks` | Escalation / exception task |

### Gemini Usage

- Used to **polish** tool output into conversational prose (`_conversational_reply`).
- If `GEMINI_API_KEY` is empty, **template fallbacks** are used instead.
- System prompt enforces: never calculate EV/probabilities yourself; cite exact tool numbers; refer to borrowers as `Legal Name (customer_code)`.

### Dependencies Listed but Unused

`langgraph` and `langchain-core` are in `requirements.txt` but **not imported** anywhere. Orchestration is custom Python in `orchestrator.py`. **PuLP** is used.

---

## 8. Guardrails and Compliance

`GuardrailEngine` (`backend/app/guardrails/engine.py`) runs **deterministic checks** and an **approval decision tree** (`classify_decision`), configured via `backend/content/guardrail_config.json`.

| Check | Result | Action |
|-------|--------|--------|
| `flag_deceased = 1` | **Blocked** | Specialist queue `deceased_escalation` |
| `flag_legal_entity = 1` | **Blocked** | Specialist queue `corporate_collections` |
| `flag_under_law_protection = 1` | **Blocked** | Specialist queue `law_protection_review` |
| Recovery rate outside configured RR bounds | **Blocked** | Compliance / block |
| `vulnerability_status != "None"` | **Warning** + **high** risk | `pending_approval` → manager queue |
| `ood_flag = true` | **Warning** + **high** risk | `pending_approval` → manager queue |
| RR near bounds / high EV | **Requires approval** | Risk tier medium/high → manager queue |
| Clean pass | **Passed** / low risk | Recommendation may proceed |

Recommendations include: `within_limits`, `requires_approval`, `approver_queue`, `risk_tier`, `alternatives`, `customer_explanation`.

Workflow tasks appear in `/workflows`. Managers/compliance/admin can **Approve / Reject / Escalate** with a resolution note; analysts can acknowledge/resolve open tasks.

---

## 9. Users, Roles, and Security

### Authentication

JWT (HS256) email/password login is implemented.

| Mechanism | Implementation | Security Level |
|-----------|----------------|----------------|
| User identity | `app_users` table (email, bcrypt hash, role) | Server-side |
| API auth | `Authorization: Bearer <token>` on protected routes | Required (401 if missing) |
| Role | Claim in JWT from authenticated user record | Server-enforced RBAC |
| Frontend session | Token in `localStorage` + cookie; `AuthProvider` + Next.js middleware | Route redirects to `/login` |
| Sidebar gating | Links filtered by role permissions | Plus soft path permission checks |
| CORS | `CORS_ORIGINS` env (default `http://localhost:3000`) | Origin restriction |

Seeded accounts (password `Settlement1!`): `analyst@`, `manager@`, `stakeholder@`, `compliance@`, `admin@` @ `settlement.ai`.

Roles and permissions: `analyst`, `manager`, `stakeholder`, `compliance`, `admin` — see `backend/app/auth/rbac.py` and `frontend/lib/roles.ts`.

### Audit Trail

The backend persists:
- `agent_conversations` — conversation metadata with `user_id` = authenticated user email
- `agent_messages` — user/assistant messages with intent and metadata JSON
- `agent_tool_calls` — tool inputs/outputs and duration
- `agent_recommendations` — settlement recommendations with guardrail status
- `agent_audit_trail` — event log with `actor_id` = authenticated user email

### Database Credentials (Docker)

Postgres user/password/database are hardcoded in `docker-compose.yml` (`settlement` / `settlement` / `settlement_ai`). Suitable for local demo only.

---

## 10. Configuration

### Environment Variables

| Variable | Default | Used By |
|----------|---------|---------|
| `GEMINI_API_KEY` | `""` | Backend — Gemini client |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | Backend |
| `DATABASE_URL` | `postgresql+asyncpg://settlement:settlement@localhost:5432/settlement_ai` | Backend, seed script |
| `CORS_ORIGINS` | `http://localhost:3000` | Backend CORS middleware |
| `JWT_SECRET` | `settlement-ai-dev-secret-change-me` | Backend JWT signing |
| `JWT_EXPIRE_MINUTES` | `480` | Backend token lifetime |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend API client |

Template: `.env.example` at repository root.

### Local Development (without Docker)

- **Backend:** Python 3.12 required (`asyncpg` does not build on Python 3.14 on Windows per README).
- **Frontend:** `npm run dev` on port 3000.
- **Database:** Postgres with pgvector must be running; run `python scripts/seed_db.py` manually.

---

## 11. Testing

### What Exists

| Type | Location | Scope |
|------|----------|-------|
| Hero EV validation | `backend/scripts/validate_hero.py` | Standalone math check for borrower 243445 (no DB) |

### What Does Not Exist

- No `pytest`, `unittest`, or `tests/` directory in backend
- No Jest, Vitest, Cypress, or Playwright in frontend
- No CI/CD pipeline (no `.github/workflows` in the project root)
- No integration or end-to-end tests
- No load or performance tests

---

## 12. Deployment and Maintenance

### Docker Compose (`docker-compose.yml`)

Three services:

| Service | Image/Build | Port | Notes |
|---------|-------------|------|-------|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | Persistent volume `postgres_data`; schema on first init |
| `backend` | `./backend/Dockerfile` | 8000 | Seeds DB on start; `--reload` enabled; source mounted |
| `frontend` | `./frontend/Dockerfile` | 3000 | Runs `npm run dev` (not production build) |

**Quick start:**
```bash
cp .env.example .env   # set GEMINI_API_KEY
docker compose up --build
```

If seeding fails after a partial run: `docker compose down -v && docker compose up --build`.

### Dockerfiles

- **Backend:** Python 3.12-slim, installs `requirements.txt`, exposes 8000. Compose overrides CMD with seed + reload.
- **Frontend:** Node 20 Alpine, runs **dev server** (`npm run dev`). `next.config.js` sets `output: "standalone"` for production, but Compose does not use it.

### Maintenance Operations

| Task | How |
|------|-----|
| Re-seed data | Restart backend container (runs `seed_db.py`) or run script manually |
| Re-ingest documents | `POST /api/documents/ingest` or restart backend (lifespan ingest) |
| Reset database | `docker compose down -v` |
| Schema changes | Edit `backend/db/schema.sql`; requires volume reset for existing DBs |
| Runtime migration | Only `agent_messages` CREATE IF NOT EXISTS in `main.py` lifespan |

### No Production Deployment Config

There is no Kubernetes manifest, Terraform, cloud-specific config, reverse proxy, TLS termination, secrets manager integration, or production-oriented Compose override in the repository.

---

## 13. Performance Considerations

### What the Code Does for Performance

| Area | Approach |
|------|----------|
| Database reads | Async SQLAlchemy + asyncpg; indexed columns on offer grid, recommended offers, SHAP |
| Offer optimization | PuLP CBC MILP over offer-grid rows (single or portfolio) |
| Chat streaming | SSE reduces perceived latency; tool events emitted before final answer |
| Dashboard | One aggregated `/api/dashboard` call instead of many round-trips |
| Frontend fetching | `cache: "no-store"` on GET requests for fresh data |
| RAG search | Loads **all** document chunks into memory and scores in Python — acceptable for ~5 small docs |

### Bottlenecks and Limits (As Implemented)

- **RAG at scale:** Full-table scan + Python cosine similarity will not scale beyond small document sets.
- **No connection pooling config:** Default SQLAlchemy pool settings only.
- **No caching layer:** No Redis or HTTP cache headers beyond SSE `no-cache`.
- **Gemini latency:** Each polished reply awaits an external API call when key is set.
- **Dev-mode frontend in Docker:** `npm run dev` is slower and not optimized for production traffic.
- **No rate limiting** on API endpoints.

---

## 14. Gaps, Weak Points, and Improvement Suggestions

All items below are observed from the codebase and are practical next steps.

### Critical Gaps

| Gap | Evidence | Suggestion |
|-----|----------|------------|
| **Simulated ML, not live `.pkl` models** | ModelScorer uses deterministic formulas; SHAP is seeded | Wire real scoring bundles when available |
| **No automated tests** | Only `validate_hero.py` | Add pytest for API/guardrails/MILP; Playwright for demo flows |
| **No CI/CD** | No project workflows | GitHub Actions: lint, test, build images on PR |

### Security Weaknesses

| Issue | Suggestion |
|-------|------------|
| Hardcoded DB credentials in Compose | Use secrets/env files; different creds per environment |
| Local JWT secret default | Set a strong `JWT_SECRET` per environment; rotate periodically |
| No refresh tokens / OIDC | Prefer Azure AD / OIDC for enterprise SSO when ready |
| Some agent helper routes lightly gated | Documents/workflows now JWT+RBAC gated; keep reviewing new routes |

### Architecture / Code Quality

| Issue | Evidence | Suggestion |
|-------|----------|------------|
| Unused dependencies | `langgraph`, `langchain-core` in requirements | Remove or implement LangGraph orchestration as spec suggests |
| Dead imports | `borrowers.py` imports unused `AgentOrchestrator`, etc. | Clean up imports |
| Duplicate schema migration | `agent_messages` in both `schema.sql` and `main.py` | Consolidate into one migration strategy (Alembic) |
| RAG pseudo-embeddings | `_simple_embed()` hash-based | Use real embeddings (e.g. Gemini embedding API) for production relevance |
| Document Q&A returns raw context | `RAGService.answer()` does not call LLM | Add LLM synthesis step for `/documents` page answers |
| Intent classifier is brittle | Keyword lists in `orchestrator.py` | Consider LLM-based routing or expand test coverage for edge phrases |

### Deployment Gaps

| Issue | Suggestion |
|-------|------------|
| Frontend runs dev server in Docker | Multi-stage Dockerfile: `npm run build` + `node server.js` (standalone) |
| Backend runs with `--reload` in Compose | Use production Uvicorn settings (no reload, workers) |
| No health-dependent frontend start | Frontend `depends_on: backend` only — no healthcheck |
| No backup/restore docs | Document Postgres volume backup for demo data persistence |
| No monitoring/observability | Add structured logging, request tracing, metrics (Prometheus/OpenTelemetry) |

### Data / Schema Gaps

| Issue | Suggestion |
|-------|------------|
| No formal migrations | Adopt Alembic for schema versioning |
| `idx_document_embedding` on `chunk_id`, not embedding | Add pgvector IVFFlat/HNSW index if real embeddings are used |
| Seeded data only | Plan ETL or API integration for production portfolio data |

### Frontend Gaps

| Issue | Suggestion |
|-------|------------|
| Inconsistent error UX | Some pages only `console.error` on failure |
| `chatSync` unused | Remove or use as fallback when streaming fails |
| No ESLint config file | Add `.eslintrc` for consistent linting |

---

## 15. Demo Scenarios (Verified Against Seed Data)

The README demo script exercises these flows:

1. **Sign in** — Use a seeded role account (e.g. `analyst@settlement.ai`).
2. **Recommend via Agent (name + code)** — From Borrowers, copy a legal name and ask e.g. `Recommend a settlement for <Name> <code>`.
3. **Payments / rescore** — `Payment history for <Name> (<code>)`; `Rescore borrower <Name> <code>`.
4. **Borrower directory** — `/borrowers` lists all seeded customers; open any profile for offer grid and optimal offer.
5. **Guardrail / HITL** — Vulnerable/OOD borrowers → `pending_approval`; manager Approve/Reject in **Workflows**.
6. **Portfolio dashboard** — KPIs and segment chart from seeded aggregates.
7. **Portfolio MILP** — `Optimize portfolio with RR capped at 50%` or Strategy frontier what-if.
8. **Document Q&A** — *"What is the max recovery rate?"* → 20–80% from `recovery-rate-policy.md`.

Edge case borrowers for testing guardrails (present among the 100 seeded customers):

| Flag pattern | Expected Behavior |
|--------------|-------------------|
| Deceased | Blocked + `deceased_escalation` workflow |
| Legal entity / Corporate | Blocked or corporate queue routing |
| Vulnerable | Warning + typically `pending_approval` |
| Out-of-distribution | Warning + typically `pending_approval` |

---

## 16. Project Structure Reference

```
MVP/
├── .env.example
├── docker-compose.yml
├── README.md
├── Settlement_Portfolio_Intelligence_Agent.md   ← spec checklist
├── docs/
│   └── SYSTEM_DOCUMENTATION.md          ← this file
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt                 ← includes pulp
│   ├── content/guardrail_config.json
│   ├── db/schema.sql
│   ├── scripts/
│   │   ├── seed_db.py
│   │   └── validate_hero.py
│   └── app/
│       ├── main.py
│       ├── agents/orchestrator.py
│       ├── api/routes/
│       ├── guardrails/engine.py
│       ├── services/                    ← scoring, model_scorer, optimizer
│       ├── models/entities.py
│       ├── rag/service.py
│       ├── repositories/borrower.py
│       └── tools/service.py
├── frontend/
│   ├── app/                             (pages per route, incl. workflows)
│   ├── components/                      (chat, ui, layout, Sidebar)
│   └── lib/                             (api, roles, format, chartTheme)
└── content/
    ├── docs/                            (RAG policy markdown)
    ├── decision-intelligence-agent-specification.md
    └── mvp-mock-data-reference.md
```

---

## 17. Summary

The Settlement Portfolio AI Agent MVP is a **decision intelligence platform** that combines seeded settlement analytics, a **simulated ModelScorer**, **PuLP MILP** offer/portfolio optimization, compliance guardrails with HITL approval routing, and a Gemini-polished conversational interface. Users sign in with role-based accounts; chat resolves borrowers by **legal name + customer code**; the frontend provides a permission-aware dashboard including Workflows, Documents, and Monitoring; Docker Compose enables one-command local deployment.

Remaining gaps for production readiness include **live `.pkl` model integration**, **parquet/CRM ETL**, **automated testing**, **enterprise SSO**, and **production deployment configuration**. Spec progress is tracked in `Settlement_Portfolio_Intelligence_Agent.md`.
