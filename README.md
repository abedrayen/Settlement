# Settlement Portfolio AI Agent — MVP

Decision Intelligence Layer for debt settlement portfolios. Ask questions in plain English; receive model-backed, compliance-gated answers with **PuLP MILP** optimization and HITL approval workflows.

## Quick Start

```bash
cp .env.example .env
# Set GEMINI_API_KEY in .env (JWT_SECRET is set in .env.example for local use)

docker compose up --build
```

If the database seed fails after a previous attempt, reset the volume and retry:

```bash
docker compose down -v
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### Sign in

Open http://localhost:3000/login. Seeded accounts (password for all: `Settlement1!`):

| Email | Role |
|-------|------|
| `analyst@settlement.ai` | Collection Analyst |
| `manager@settlement.ai` | Operational Manager |
| `admin@settlement.ai` | Admin |

Role is assigned from the user record (JWT). There is no client-side role switcher.

### Navigation (six primary views)

| View | Route | Roles |
|------|-------|-------|
| Collection Workspace | `/workspace` | Analyst, Manager, Admin |
| Settlement Optimization | `/optimization` | Analyst, Manager, Admin |
| Portfolio Monitoring | `/portfolio` | Manager, Admin |
| Approvals & Exceptions | `/approvals` | Manager, Admin |
| Executive Dashboard | `/executive` | Manager, Admin |
| AI Assistant | `/assistant` | All |

Secondary: Documents, Model Health, Audit, Settings (admin).

## Demo Script

1. Open http://localhost:3000 and sign in as `analyst@settlement.ai`
2. Open **Collection Workspace** — browse borrowers, open a profile, review payment history + offer grid
3. Click **Submit for Approval** on a borrower, or ask the **AI Assistant**:  
   `Recommend a settlement for James Smith 243445`
4. Try: `Payment history for James Smith (243445)` and `Rescore borrower James Smith 243445`
5. Open **Settlement Optimization** — view frontier (analysts read-only for portfolio jobs)
6. Sign in as `manager@settlement.ai` → **Approvals & Exceptions** — Approve/Reject/Escalate
7. Open **Portfolio Monitoring** and **Executive Dashboard** — KPIs, heatmap, automation, bottlenecks
8. In **Documents**, query: `What is the max recovery rate?` — expect 20–80% from policy

Borrowers are always referred to as **`Legal Name (customer_code)`** in chat, cards, and workflows.

## Seed Data

| Entity | Count |
|--------|-------|
| App users | 3 (analyst, manager, admin) |
| Customers | 100 (legal name + customer code) |
| Settlements | 100 |
| Accounts | ~150 |
| Offer grid | 900 (9 combos per borrower) |

Reseed: `docker compose exec backend python scripts/seed_db.py --force`

See [content/mvp-mock-data-reference.md](content/mvp-mock-data-reference.md) for full reference.

## Decision engine (as implemented)

| Capability | Implementation |
|------------|----------------|
| EV formula | `PoAPP × PoA × PoF × (Balance × RR)` in `backend/app/services/scoring.py` |
| T5 ModelScorer | Simulated deterministic rescoring (`POST /api/borrowers/{id}/score`) |
| T2 OfferOptimiser | **PuLP CBC MILP** — single borrower + portfolio assignment |
| Frontier what-if | Portfolio MILP under RR / P(fulfill) constraints |
| Guardrails + HITL | Risk tiers, `pending_approval`, Approve/Reject/Escalate in **Approvals** |

Live `.pkl` models and parquet ETL are **not** included — scores are simulated/seeded.

## API Endpoints

Protected routes require `Authorization: Bearer <access_token>` from `POST /api/auth/login`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Email/password login → JWT |
| GET | `/api/auth/me` | Current user |
| POST | `/api/chat` | Agent chat (SSE stream) |
| POST | `/api/chat/sync` | Agent chat (sync) |
| GET | `/api/borrowers` | Borrower directory |
| GET | `/api/borrowers/{id}` | Borrower profile |
| GET | `/api/borrowers/{id}/payments` | Payment history |
| POST | `/api/borrowers/{id}/submit-approval` | Create HITL approval task |
| POST | `/api/borrowers/{id}/score` | On-demand simulated model score |
| POST | `/api/borrowers/{id}/what-if` | Constrained MILP offer |
| GET | `/api/portfolio/kpis` | Portfolio KPIs |
| GET | `/api/executive/kpis` | Executive dashboard aggregates |
| GET | `/api/frontier` | Efficient frontier + MILP constraint sim |
| GET | `/api/monitoring` | Model health |
| POST | `/api/documents/query` | RAG document Q&A |
| GET | `/api/workflows` | Escalation / approval tasks |
| GET | `/api/workflows/kpis` | Approval rate / SLA KPIs |
| PATCH | `/api/workflows/{id}` | Acknowledge / approve / reject / escalate |
| GET | `/api/audit/recommendations` | Audit trail |

## Project Structure

```
MVP/
├── backend/          # FastAPI + orchestrator + PuLP + tools
│   └── app/services/ # scoring.py, model_scorer.py, optimizer.py
├── frontend/         # Next.js 14 dashboard + chat
├── content/          # Business specs + policy docs for RAG
├── docs/             # SYSTEM_DOCUMENTATION.md (as-built)
├── Settlement_Portfolio_Intelligence_Agent.md  # Spec checklist
└── docker-compose.yml
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Default: `gemini-3-flash-preview` |
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | HMAC secret for access tokens |
| `JWT_EXPIRE_MINUTES` | Token lifetime (default 480) |
| `CORS_ORIGINS` | Allowed frontend origins |

## Development (without Docker)

> **Note:** Local backend install requires **Python 3.12**. Python 3.14 on Windows cannot build `asyncpg` wheels yet. Use Docker for the simplest setup.

**Backend:**
```bash
cd backend
pip install -r requirements.txt
# Start PostgreSQL with pgvector locally
python scripts/seed_db.py
# Force refresh of synthetic demo data:
# python scripts/seed_db.py --force
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Further reading

- [docs/OPERATIONAL_ARCHITECTURE_AND_SYSTEM_DOCUMENTATION.md](docs/OPERATIONAL_ARCHITECTURE_AND_SYSTEM_DOCUMENTATION.md) — **full operational architecture & system documentation** (end-to-end workflows, data flows, RBAC, APIs, runbook)
- [docs/SYSTEM_DOCUMENTATION.md](docs/SYSTEM_DOCUMENTATION.md) — shorter as-built companion
- [Settlement_Portfolio_Intelligence_Agent.md](Settlement_Portfolio_Intelligence_Agent.md) — specification checklist (done / partial / not started)
- [CURSOR_IMPLEMENTATION_GUIDE_Settlement_Portfolio_AI.md](CURSOR_IMPLEMENTATION_GUIDE_Settlement_Portfolio_AI.md) — six-view IA guide
