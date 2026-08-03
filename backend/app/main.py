from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import agent, audit, auth, borrowers, dashboard, jobs, portfolio, strategy
from app.api.routes import settings as settings_routes
from app.config import settings
from app.database import AsyncSessionLocal
from app.rag.service import RAGService

_MIGRATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS agent_messages (
        message_id UUID PRIMARY KEY,
        conversation_id UUID REFERENCES agent_conversations(conversation_id),
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        intent VARCHAR(50),
        metadata_json JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_portfolio_kpis_monthly (
        kpi_id SERIAL PRIMARY KEY,
        ref_year_month VARCHAR(6) NOT NULL,
        segment VARCHAR(50) NOT NULL DEFAULT 'All',
        expected_value DOUBLE PRECISION,
        actual_collections DOUBLE PRECISION,
        realization_rate DOUBLE PRECISION,
        borrower_count INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_kpis_month ON fact_portfolio_kpis_monthly(ref_year_month, segment)",
    "ALTER TABLE dim_customer ADD COLUMN IF NOT EXISTS legal_name VARCHAR(200)",
    "CREATE INDEX IF NOT EXISTS idx_customer_legal_name ON dim_customer (legal_name)",
    """
    CREATE TABLE IF NOT EXISTS app_users (
        id UUID PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        full_name VARCHAR(200) NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users (email)",
    "ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS risk_tier VARCHAR(20)",
    "ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS priority INTEGER",
    "ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS conversation_id UUID",
    "ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS decision_payload JSONB",
    "ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS resolution_note TEXT",
    "ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS resolved_by VARCHAR(255)",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as session:
        for stmt in _MIGRATE_STATEMENTS:
            await session.execute(text(stmt))
        await session.commit()
        rag = RAGService(session)
        await rag.ingest_documents()
    yield


app = FastAPI(title="Settlement Portfolio AI Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(agent.router)
app.include_router(borrowers.router)
app.include_router(portfolio.router)
app.include_router(strategy.router)
app.include_router(audit.router)
app.include_router(settings_routes.router)
app.include_router(jobs.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
