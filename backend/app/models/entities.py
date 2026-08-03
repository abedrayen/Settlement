from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.database import Base


class DimCustomer(Base):
    __tablename__ = "dim_customer"
    customer_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    birth_date: Mapped[date | None] = mapped_column(Date)
    age: Mapped[int | None] = mapped_column(Integer)
    flag_deceased: Mapped[int] = mapped_column(Integer, default=0)
    flag_legal_entity: Mapped[int] = mapped_column(Integer, default=0)
    flag_company_is_active: Mapped[int] = mapped_column(Integer, default=1)
    legal_entity_type: Mapped[int] = mapped_column(Integer, default=0)
    post_code: Mapped[int | None] = mapped_column(Integer)
    nomos: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    occupation: Mapped[str | None] = mapped_column(String(100))
    customer_type: Mapped[str | None] = mapped_column(String(50))
    aml_risk: Mapped[str | None] = mapped_column(String(20))
    segment: Mapped[str | None] = mapped_column(String(50))
    flag_campaign: Mapped[int] = mapped_column(Integer, default=0)
    flag_corporate: Mapped[int] = mapped_column(Integer, default=0)
    flag_legal: Mapped[int] = mapped_column(Integer, default=0)
    flag_under_law_protection: Mapped[int] = mapped_column(Integer, default=0)
    vulnerability_status: Mapped[str] = mapped_column(String(50), default="None")
    ood_flag: Mapped[bool] = mapped_column(Boolean, default=False)


class DimRegion(Base):
    __tablename__ = "dim_region"
    region_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_code: Mapped[int | None] = mapped_column(Integer)
    nomos: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))


class DimChannel(Base):
    __tablename__ = "dim_channel"
    channel_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_channel_name: Mapped[str | None] = mapped_column(String(100))
    channel_group: Mapped[str | None] = mapped_column(String(50))


class DimProduct(Base):
    __tablename__ = "dim_product"
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_unit: Mapped[str | None] = mapped_column(String(50))
    product: Mapped[str | None] = mapped_column(String(50))


class DimPortfolio(Base):
    __tablename__ = "dim_portfolio"
    portfolio_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_name: Mapped[str | None] = mapped_column(String(100))
    portfolio_group: Mapped[str | None] = mapped_column(String(50))


class FactSettlement(Base):
    __tablename__ = "fact_settlements_monthly"
    settlement_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_code: Mapped[int] = mapped_column(Integer, ForeignKey("dim_customer.customer_code"))
    ref_year_month: Mapped[str | None] = mapped_column(String(6))
    reference_date: Mapped[date | None] = mapped_column(Date)
    last_working_date: Mapped[date | None] = mapped_column(Date)
    portfolio_name: Mapped[str | None] = mapped_column(String(100))
    settlement_status: Mapped[str | None] = mapped_column(String(50))
    settlement_status_date: Mapped[date | None] = mapped_column(Date)
    settlement_created: Mapped[date | None] = mapped_column(Date)
    settlement_activation_date: Mapped[date | None] = mapped_column(Date)
    settlement_current_month: Mapped[int | None] = mapped_column(Integer)
    settlement_duration: Mapped[int | None] = mapped_column(Integer)
    settlement_nr_installments: Mapped[int | None] = mapped_column(Integer)
    settlement_amount: Mapped[float | None] = mapped_column(Float)
    settlement_principal_amount: Mapped[float | None] = mapped_column(Float)
    settlement_remaining_amount: Mapped[float | None] = mapped_column(Float)
    settlement_discount_amount: Mapped[float | None] = mapped_column(Float)
    settlement_down_payment_amnt: Mapped[float | None] = mapped_column(Float)
    settlement_kept_percentage: Mapped[float | None] = mapped_column(Float)
    settlement_type_description: Mapped[str | None] = mapped_column(String(100))
    settlement_arrears_days: Mapped[int | None] = mapped_column(Integer)
    settlement_bucket: Mapped[int | None] = mapped_column(Integer)
    settlement_arrears_amount: Mapped[float | None] = mapped_column(Float)
    settlement_paid_amount: Mapped[float | None] = mapped_column(Float)
    past_installments_amnt: Mapped[float | None] = mapped_column(Float)
    connected_loans: Mapped[int | None] = mapped_column(Integer)
    total_balance_connected_loans: Mapped[float | None] = mapped_column(Float)
    accounting_balance_connected_loans: Mapped[float | None] = mapped_column(Float)
    written_off_amount_connected_loans: Mapped[float | None] = mapped_column(Float)
    principal_amount_connected_loans: Mapped[float | None] = mapped_column(Float)
    assignment_channel_name: Mapped[str | None] = mapped_column(String(100))
    channel_group: Mapped[str | None] = mapped_column(String(50))
    payments_6m: Mapped[float | None] = mapped_column(Float)
    latest_payment_date: Mapped[date | None] = mapped_column(Date)
    days_from_last_activity: Mapped[int | None] = mapped_column(Integer)
    latest_activity_type: Mapped[str | None] = mapped_column(String(50))
    latest_contact_type: Mapped[str | None] = mapped_column(String(50))
    activity_days_3m: Mapped[int | None] = mapped_column(Integer)
    right_party_contact_activities_3m: Mapped[int | None] = mapped_column(Integer)
    nfct_rpc_activities_3m: Mapped[int | None] = mapped_column(Integer)
    sms_activities_3m: Mapped[int | None] = mapped_column(Integer)


class FactAccount(Base):
    __tablename__ = "fact_accounts_monthly"
    account_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_code: Mapped[int] = mapped_column(Integer, ForeignKey("dim_customer.customer_code"))
    dpd: Mapped[int | None] = mapped_column(Integer)
    bucket: Mapped[int | None] = mapped_column(Integer)
    denouncement_amount: Mapped[float | None] = mapped_column(Float)
    debt_amount: Mapped[float | None] = mapped_column(Float)
    total_balance: Mapped[float | None] = mapped_column(Float)
    accounting_balance: Mapped[float | None] = mapped_column(Float)
    written_off_amount: Mapped[float | None] = mapped_column(Float)
    principal_amount: Mapped[float | None] = mapped_column(Float)
    interest_custom_type: Mapped[str | None] = mapped_column(String(50))
    account_open_date: Mapped[date | None] = mapped_column(Date)
    account_current_month: Mapped[int | None] = mapped_column(Integer)
    fixed_rate: Mapped[float | None] = mapped_column(Float)
    total_interest_rate: Mapped[float | None] = mapped_column(Float)
    spread: Mapped[float | None] = mapped_column(Float)
    assignment_channel_name: Mapped[str | None] = mapped_column(String(100))
    channel_group: Mapped[str | None] = mapped_column(String(50))
    business_unit: Mapped[str | None] = mapped_column(String(50))
    product: Mapped[str | None] = mapped_column(String(50))


class BridgeMapping(Base):
    __tablename__ = "bridge_settlement_customer_account"
    settlement_code: Mapped[int] = mapped_column(
        Integer, ForeignKey("fact_settlements_monthly.settlement_code"), primary_key=True
    )
    customer_code: Mapped[int] = mapped_column(Integer, ForeignKey("dim_customer.customer_code"))
    account_code: Mapped[int] = mapped_column(Integer, ForeignKey("fact_accounts_monthly.account_code"))


class FactApplication(Base):
    __tablename__ = "fact_applications"
    application_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_code: Mapped[int] = mapped_column(Integer)
    customer_id: Mapped[int | None] = mapped_column(Integer)
    settlement_code: Mapped[int] = mapped_column(Integer)
    portfolio: Mapped[str | None] = mapped_column(String(100))
    portfolio_group: Mapped[str | None] = mapped_column(String(50))
    customer_segment: Mapped[str | None] = mapped_column(String(50))
    application_status: Mapped[str | None] = mapped_column(String(50))
    pipeline_status: Mapped[str | None] = mapped_column(String(50))
    qc_application_status: Mapped[str | None] = mapped_column(String(50))
    current_stage: Mapped[str | None] = mapped_column(String(50))
    current_stage_start_date: Mapped[date | None] = mapped_column(Date)
    current_step: Mapped[str | None] = mapped_column(String(50))
    start_date: Mapped[date | None] = mapped_column(Date)
    creation_date: Mapped[date | None] = mapped_column(Date)
    submission_date: Mapped[date | None] = mapped_column(Date)
    approval_date: Mapped[date | None] = mapped_column(Date)
    assignment_channel: Mapped[str | None] = mapped_column(String(100))
    application_channel: Mapped[str | None] = mapped_column(String(100))
    assigned_officer: Mapped[str | None] = mapped_column(String(100))
    initial_tenor: Mapped[int | None] = mapped_column(Integer)
    initial_installment_amount: Mapped[float | None] = mapped_column(Float)
    final_tenor: Mapped[int | None] = mapped_column(Integer)
    final_installment_amount: Mapped[float | None] = mapped_column(Float)
    final_solution_type: Mapped[str | None] = mapped_column(String(50))
    settlement_amount: Mapped[float | None] = mapped_column(Float)
    flag_law: Mapped[int] = mapped_column(Integer, default=0)


class FactPayment(Base):
    __tablename__ = "fact_payments"
    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_code: Mapped[int] = mapped_column(Integer)
    payment_date: Mapped[date | None] = mapped_column(Date)
    payment_amount: Mapped[float | None] = mapped_column(Float)
    payment_type: Mapped[str | None] = mapped_column(String(50))


class FactActivity(Base):
    __tablename__ = "fact_activities"
    activity_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_code: Mapped[int] = mapped_column(Integer)
    settlement_code: Mapped[int | None] = mapped_column(Integer)
    activity_date: Mapped[date | None] = mapped_column(Date)
    activity_type: Mapped[str | None] = mapped_column(String(50))
    contact_type: Mapped[str | None] = mapped_column(String(50))
    outcome: Mapped[str | None] = mapped_column(String(100))


class FactPortfolioKpiMonthly(Base):
    __tablename__ = "fact_portfolio_kpis_monthly"
    kpi_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ref_year_month: Mapped[str] = mapped_column(String(6))
    segment: Mapped[str] = mapped_column(String(50), default="All")
    expected_value: Mapped[float | None] = mapped_column(Float)
    actual_collections: Mapped[float | None] = mapped_column(Float)
    realization_rate: Mapped[float | None] = mapped_column(Float)
    borrower_count: Mapped[int | None] = mapped_column(Integer)


class FactOfferGridScore(Base):
    __tablename__ = "fact_offer_grid_scores"
    grid_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_code: Mapped[int] = mapped_column(Integer)
    settlement_code: Mapped[int] = mapped_column(Integer)
    recovery_rate: Mapped[float] = mapped_column(Float)
    installments: Mapped[int] = mapped_column(Integer)
    p_application: Mapped[float] = mapped_column(Float)
    p_acceptance: Mapped[float] = mapped_column(Float)
    p_fulfillment: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(20))
    scored_at: Mapped[date | None] = mapped_column(Date)


class FactRecommendedOffer(Base):
    __tablename__ = "fact_recommended_offers"
    recommendation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_code: Mapped[int] = mapped_column(Integer)
    settlement_code: Mapped[int] = mapped_column(Integer)
    optimal_rr: Mapped[float] = mapped_column(Float)
    optimal_installments: Mapped[int] = mapped_column(Integer)
    expected_value: Mapped[float] = mapped_column(Float)
    mip_gap: Mapped[float] = mapped_column(Float)
    ref_year_month: Mapped[str] = mapped_column(String(6))
    model_version: Mapped[str] = mapped_column(String(20))
    p_application: Mapped[float] = mapped_column(Float)
    p_acceptance: Mapped[float] = mapped_column(Float)
    p_fulfillment: Mapped[float] = mapped_column(Float)


class FactEfficientFrontier(Base):
    __tablename__ = "fact_efficient_frontier"
    frontier_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50))
    portfolio_ev: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[float] = mapped_column(Float)
    min_p_fulfill: Mapped[float | None] = mapped_column(Float)
    max_rr: Mapped[float | None] = mapped_column(Float)
    ref_year_month: Mapped[str] = mapped_column(String(6))


class FactModelMonitoring(Base):
    __tablename__ = "fact_model_monitoring"
    monitoring_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(50))
    metric_name: Mapped[str] = mapped_column(String(50))
    metric_value: Mapped[float] = mapped_column(Float)
    baseline_value: Mapped[float] = mapped_column(Float)
    ref_year_month: Mapped[str] = mapped_column(String(6))
    alert_flag: Mapped[bool] = mapped_column(Boolean, default=False)


class FactShapExplanation(Base):
    __tablename__ = "fact_shap_explanations"
    shap_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_code: Mapped[int] = mapped_column(Integer)
    model_name: Mapped[str] = mapped_column(String(50))
    feature_name: Mapped[str] = mapped_column(String(100))
    shap_value: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(20))
    scored_at: Mapped[date | None] = mapped_column(Date)


class AgentConversation(Base):
    __tablename__ = "agent_conversations"
    conversation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))
    domain: Mapped[str | None] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    message_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("agent_conversations.conversation_id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"
    tool_call_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    tool_name: Mapped[str] = mapped_column(String(50))
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class AgentRecommendation(Base):
    __tablename__ = "agent_recommendations"
    recommendation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    customer_code: Mapped[int] = mapped_column(Integer)
    settlement_code: Mapped[int] = mapped_column(Integer)
    recommended_rr: Mapped[float] = mapped_column(Float)
    recommended_installments: Mapped[int] = mapped_column(Integer)
    expected_value: Mapped[float] = mapped_column(Float)
    p_application: Mapped[float] = mapped_column(Float)
    p_acceptance: Mapped[float] = mapped_column(Float)
    p_fulfillment: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(20))
    mip_gap: Mapped[float] = mapped_column(Float)
    guardrail_passed: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentAuditTrail(Base):
    __tablename__ = "agent_audit_trail"
    audit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(50))
    actor_id: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    event_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"
    task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_type: Mapped[str] = mapped_column(String(50))
    customer_code: Mapped[int | None] = mapped_column(Integer)
    settlement_code: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_queue: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(100))
    risk_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conversation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    decision_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_name: Mapped[str] = mapped_column(String(200))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))


class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
