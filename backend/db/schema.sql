-- Settlement Portfolio AI Agent — PostgreSQL Schema
CREATE EXTENSION IF NOT EXISTS vector;

-- Dimension tables
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_code INTEGER PRIMARY KEY,
    legal_name VARCHAR(200),
    birth_date DATE,
    age INTEGER,
    flag_deceased INTEGER DEFAULT 0,
    flag_legal_entity INTEGER DEFAULT 0,
    flag_company_is_active INTEGER DEFAULT 1,
    legal_entity_type INTEGER DEFAULT 0,
    post_code INTEGER,
    nomos VARCHAR(100),
    region VARCHAR(100),
    occupation VARCHAR(100),
    customer_type VARCHAR(50),
    aml_risk VARCHAR(20),
    segment VARCHAR(50),
    flag_campaign INTEGER DEFAULT 0,
    flag_corporate INTEGER DEFAULT 0,
    flag_legal INTEGER DEFAULT 0,
    flag_under_law_protection INTEGER DEFAULT 0,
    vulnerability_status VARCHAR(50) DEFAULT 'None',
    ood_flag BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_customer_legal_name ON dim_customer (legal_name);

CREATE TABLE IF NOT EXISTS dim_region (
    region_id SERIAL PRIMARY KEY,
    post_code INTEGER,
    nomos VARCHAR(100),
    region VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS dim_channel (
    channel_id SERIAL PRIMARY KEY,
    assignment_channel_name VARCHAR(100),
    channel_group VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id SERIAL PRIMARY KEY,
    business_unit VARCHAR(50),
    product VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_portfolio (
    portfolio_id SERIAL PRIMARY KEY,
    portfolio_name VARCHAR(100),
    portfolio_group VARCHAR(50)
);

-- Fact tables
CREATE TABLE IF NOT EXISTS fact_settlements_monthly (
    settlement_code INTEGER PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    ref_year_month VARCHAR(6),
    reference_date DATE,
    last_working_date DATE,
    portfolio_name VARCHAR(100),
    settlement_status VARCHAR(50),
    settlement_status_date DATE,
    settlement_created DATE,
    settlement_activation_date DATE,
    settlement_current_month INTEGER,
    settlement_duration INTEGER,
    settlement_nr_installments INTEGER,
    settlement_amount DOUBLE PRECISION,
    settlement_principal_amount DOUBLE PRECISION,
    settlement_remaining_amount DOUBLE PRECISION,
    settlement_discount_amount DOUBLE PRECISION,
    settlement_down_payment_amnt DOUBLE PRECISION,
    settlement_kept_percentage DOUBLE PRECISION,
    settlement_type_description VARCHAR(100),
    settlement_arrears_days INTEGER,
    settlement_bucket INTEGER,
    settlement_arrears_amount DOUBLE PRECISION,
    settlement_paid_amount DOUBLE PRECISION,
    past_installments_amnt DOUBLE PRECISION,
    connected_loans INTEGER,
    total_balance_connected_loans DOUBLE PRECISION,
    accounting_balance_connected_loans DOUBLE PRECISION,
    written_off_amount_connected_loans DOUBLE PRECISION,
    principal_amount_connected_loans DOUBLE PRECISION,
    assignment_channel_name VARCHAR(100),
    channel_group VARCHAR(50),
    sb_products INTEGER DEFAULT 0,
    cl_products INTEGER DEFAULT 0,
    cc_products INTEGER DEFAULT 0,
    payments_6m DOUBLE PRECISION,
    earlier_payment_date DATE,
    earlier_payment_days INTEGER,
    latest_payment_date DATE,
    latest_payment_days INTEGER,
    payments_window_6m INTEGER,
    latest_activity_date DATE,
    days_from_last_activity INTEGER,
    latest_activity_type VARCHAR(50),
    latest_contact_type VARCHAR(50),
    activity_days_3m INTEGER,
    cca_activities_3m INTEGER DEFAULT 0,
    nfctp_activities_3m INTEGER DEFAULT 0,
    capt_activities_3m INTEGER DEFAULT 0,
    nfct_rpc_activities_3m INTEGER DEFAULT 0,
    nfct_ref_activities_3m INTEGER DEFAULT 0,
    nfct_rev_activities_3m INTEGER DEFAULT 0,
    nfct_ptp_activities_3m INTEGER DEFAULT 0,
    nfct_activities_3m INTEGER DEFAULT 0,
    sms_activities_3m INTEGER DEFAULT 0,
    no_contact_activities_3m INTEGER DEFAULT 0,
    third_person_contact_activities_3m INTEGER DEFAULT 0,
    right_party_contact_activities_3m INTEGER DEFAULT 0,
    wrong_person_contact_activities_3m INTEGER DEFAULT 0,
    letter_activities_3m INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fact_accounts_monthly (
    account_code INTEGER PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    dpd INTEGER,
    bucket INTEGER,
    denouncement_amount DOUBLE PRECISION,
    debt_amount DOUBLE PRECISION,
    total_balance DOUBLE PRECISION,
    accounting_balance DOUBLE PRECISION,
    written_off_amount DOUBLE PRECISION,
    principal_amount DOUBLE PRECISION,
    interest_custom_type VARCHAR(50),
    account_open_date DATE,
    account_current_month INTEGER,
    fixed_rate DOUBLE PRECISION,
    total_interest_rate DOUBLE PRECISION,
    spread DOUBLE PRECISION,
    assignment_channel_name VARCHAR(100),
    channel_group VARCHAR(50),
    business_unit VARCHAR(50),
    product VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS bridge_settlement_customer_account (
    settlement_code INTEGER PRIMARY KEY REFERENCES fact_settlements_monthly(settlement_code),
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    account_code INTEGER REFERENCES fact_accounts_monthly(account_code)
);

CREATE TABLE IF NOT EXISTS fact_applications (
    application_code INTEGER PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    customer_id INTEGER,
    settlement_code INTEGER REFERENCES fact_settlements_monthly(settlement_code),
    portfolio VARCHAR(100),
    portfolio_group VARCHAR(50),
    customer_segment VARCHAR(50),
    application_status VARCHAR(50),
    pipeline_status VARCHAR(50),
    qc_application_status VARCHAR(50),
    current_stage VARCHAR(50),
    current_stage_start_date DATE,
    current_stage_order_in_process VARCHAR(20),
    current_step VARCHAR(50),
    start_date DATE,
    creation_date DATE,
    submission_date DATE,
    approval_date DATE,
    implementation_date DATE,
    activation_date DATE,
    cancellation_date DATE,
    rejection_date DATE,
    end_date DATE,
    assigned_officer VARCHAR(100),
    application_officer VARCHAR(100),
    application_creator VARCHAR(100),
    assignment_channel VARCHAR(100),
    application_channel VARCHAR(100),
    application_channel_group VARCHAR(50),
    initial_tenor INTEGER,
    initial_interest_rate DOUBLE PRECISION,
    initial_installment_amount DOUBLE PRECISION,
    initial_haircut_amount DOUBLE PRECISION,
    initial_downpayment_amount DOUBLE PRECISION,
    initial_restructuring_amount DOUBLE PRECISION,
    initial_solution_type VARCHAR(50),
    counter_proposal_installment DOUBLE PRECISION,
    counter_proposal_haircut_amount DOUBLE PRECISION,
    counter_proposal_restructuring_amount DOUBLE PRECISION,
    counter_proposal_downpayment DOUBLE PRECISION,
    final_tenor INTEGER,
    final_interest_rate DOUBLE PRECISION,
    final_installment_amount DOUBLE PRECISION,
    final_haircut_amount DOUBLE PRECISION,
    final_downpayment_amount DOUBLE PRECISION,
    final_restructuring_amount DOUBLE PRECISION,
    final_solution_type VARCHAR(50),
    settlement_amount DOUBLE PRECISION,
    flag_law INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fact_payments (
    payment_id SERIAL PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    payment_date DATE,
    payment_amount DOUBLE PRECISION,
    payment_type VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS fact_activities (
    activity_id SERIAL PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    settlement_code INTEGER REFERENCES fact_settlements_monthly(settlement_code),
    activity_date DATE,
    activity_type VARCHAR(50),
    contact_type VARCHAR(50),
    outcome VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS fact_portfolio_kpis_monthly (
    kpi_id SERIAL PRIMARY KEY,
    ref_year_month VARCHAR(6) NOT NULL,
    segment VARCHAR(50) NOT NULL DEFAULT 'All',
    expected_value DOUBLE PRECISION,
    actual_collections DOUBLE PRECISION,
    realization_rate DOUBLE PRECISION,
    borrower_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_portfolio_kpis_month ON fact_portfolio_kpis_monthly(ref_year_month, segment);

-- AI / Optimization tables
CREATE TABLE IF NOT EXISTS fact_offer_grid_scores (
    grid_id SERIAL PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    settlement_code INTEGER REFERENCES fact_settlements_monthly(settlement_code),
    recovery_rate DOUBLE PRECISION,
    installments INTEGER,
    p_application DOUBLE PRECISION,
    p_acceptance DOUBLE PRECISION,
    p_fulfillment DOUBLE PRECISION,
    expected_value DOUBLE PRECISION,
    model_version VARCHAR(20),
    scored_at DATE
);

CREATE TABLE IF NOT EXISTS fact_recommended_offers (
    recommendation_id SERIAL PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    settlement_code INTEGER REFERENCES fact_settlements_monthly(settlement_code),
    optimal_rr DOUBLE PRECISION,
    optimal_installments INTEGER,
    expected_value DOUBLE PRECISION,
    mip_gap DOUBLE PRECISION,
    ref_year_month VARCHAR(6),
    model_version VARCHAR(20),
    p_application DOUBLE PRECISION,
    p_acceptance DOUBLE PRECISION,
    p_fulfillment DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS fact_efficient_frontier (
    frontier_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50),
    portfolio_ev DOUBLE PRECISION,
    risk_level VARCHAR(20),
    risk_score DOUBLE PRECISION,
    min_p_fulfill DOUBLE PRECISION,
    max_rr DOUBLE PRECISION,
    ref_year_month VARCHAR(6)
);

CREATE TABLE IF NOT EXISTS fact_model_monitoring (
    monitoring_id SERIAL PRIMARY KEY,
    model_name VARCHAR(50),
    metric_name VARCHAR(50),
    metric_value DOUBLE PRECISION,
    baseline_value DOUBLE PRECISION,
    ref_year_month VARCHAR(6),
    alert_flag BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS fact_shap_explanations (
    shap_id SERIAL PRIMARY KEY,
    customer_code INTEGER REFERENCES dim_customer(customer_code),
    model_name VARCHAR(50),
    feature_name VARCHAR(100),
    shap_value DOUBLE PRECISION,
    direction VARCHAR(20),
    scored_at DATE
);

-- Agent audit tables
CREATE TABLE IF NOT EXISTS agent_conversations (
    conversation_id UUID PRIMARY KEY,
    user_id VARCHAR(100),
    role VARCHAR(50),
    domain VARCHAR(50),
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_messages (
    message_id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES agent_conversations(conversation_id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(50),
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    tool_call_id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES agent_conversations(conversation_id),
    tool_name VARCHAR(50),
    input_payload JSONB,
    output_payload JSONB,
    executed_at TIMESTAMP DEFAULT NOW(),
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS agent_recommendations (
    recommendation_id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES agent_conversations(conversation_id),
    customer_code INTEGER,
    settlement_code INTEGER,
    recommended_rr DOUBLE PRECISION,
    recommended_installments INTEGER,
    expected_value DOUBLE PRECISION,
    p_application DOUBLE PRECISION,
    p_acceptance DOUBLE PRECISION,
    p_fulfillment DOUBLE PRECISION,
    model_version VARCHAR(20),
    mip_gap DOUBLE PRECISION,
    guardrail_passed BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_audit_trail (
    audit_id UUID PRIMARY KEY,
    event_type VARCHAR(50),
    actor_id VARCHAR(100),
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    event_payload JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_tasks (
    task_id UUID PRIMARY KEY,
    customer_code INTEGER,
    settlement_code INTEGER,
    task_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'open',
    assigned_queue VARCHAR(50),
    reason VARCHAR(100),
    risk_tier VARCHAR(20),
    priority INTEGER,
    conversation_id UUID,
    decision_payload JSONB,
    resolution_note TEXT,
    resolved_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- RAG document chunks
CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id SERIAL PRIMARY KEY,
    document_name VARCHAR(200),
    chunk_index INTEGER,
    content TEXT,
    embedding vector(768)
);

-- Application users (JWT login)
CREATE TABLE IF NOT EXISTS app_users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(200) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users (email);

CREATE INDEX IF NOT EXISTS idx_offer_grid_customer ON fact_offer_grid_scores(customer_code);
CREATE INDEX IF NOT EXISTS idx_recommended_customer ON fact_recommended_offers(customer_code);
CREATE INDEX IF NOT EXISTS idx_shap_customer ON fact_shap_explanations(customer_code);
CREATE INDEX IF NOT EXISTS idx_document_embedding ON document_chunks (chunk_id);
