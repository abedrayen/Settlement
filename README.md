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
| `analyst@settlement.ai` | Collections Analyst |
| `manager@settlement.ai` | Portfolio Manager |
| `stakeholder@settlement.ai` | Senior Stakeholder |
| `compliance@settlement.ai` | Compliance Reviewer |
| `admin@settlement.ai` | Admin |

Role is assigned from the user record (JWT). There is no client-side role switcher.

## Demo Script

1. Open http://localhost:3000 and sign in as `analyst@settlement.ai`
2. In **Agent**, ask using **name + code** (open **Borrowers** first to copy a legal name), e.g.  
   `Recommend a settlement for James Smith 243445`
3. Try: `Payment history for James Smith (243445)` and `Rescore borrower James Smith 243445`
4. Open **Borrowers** — browse the seeded list, filter by segment/status, open any customer profile
5. Open **Portfolio** — verify KPIs, realisation trend, and segment chart
6. Sign in as `manager@settlement.ai` → **Strategy** (frontier what-if) or ask:  
   `Optimize portfolio with RR capped at 50%`
7. Open **Workflows** — approve/reject/escalate pending recommendations (manager/compliance/admin)
8. In **Documents**, query: `What is the max recovery rate?` — expect 20–80% from policy

Borrowers are always referred to as **`Legal Name (customer_code)`** in chat, cards, and workflows.

## Seed Data

| Entity | Count |
|--------|-------|
| App users | 5 (one per role) |
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
| Guardrails + HITL | Risk tiers, `pending_approval`, Approve/Reject/Escalate in **Workflows** |

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
| POST | `/api/borrowers/{id}/score` | On-demand simulated model score |
| POST | `/api/borrowers/{id}/what-if` | Constrained MILP offer |
| GET | `/api/portfolio/kpis` | Portfolio KPIs |
| GET | `/api/frontier` | Efficient frontier + MILP constraint sim |
| GET | `/api/monitoring` | Model health |
| POST | `/api/documents/query` | RAG document Q&A |
| GET | `/api/workflows` | Escalation / approval tasks |
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

- [docs/SYSTEM_DOCUMENTATION.md](docs/SYSTEM_DOCUMENTATION.md) — as-built architecture
- [Settlement_Portfolio_Intelligence_Agent.md](Settlement_Portfolio_Intelligence_Agent.md) — specification checklist (done / partial / not started)
