"""Schema-faithful synthetic seeder aligned to Quant_data_layout_08062026.xlsx."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.entities import (  # noqa: E402
    AppUser,
    BridgeMapping,
    DimChannel,
    DimCustomer,
    DimPortfolio,
    DimProduct,
    DimRegion,
    FactAccount,
    FactActivity,
    FactApplication,
    FactEfficientFrontier,
    FactModelMonitoring,
    FactOfferGridScore,
    FactPayment,
    FactPortfolioKpiMonthly,
    FactRecommendedOffer,
    FactSettlement,
    FactShapExplanation,
)
from app.auth.security import hash_password  # noqa: E402
from app.services.scoring import compute_ev, score_probabilities  # noqa: E402

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://settlement:settlement@postgres:5432/settlement_ai"
)

CUSTOMER_COUNT = 100
CUSTOMER_CODES = [243445 + i for i in range(CUSTOMER_COUNT)]
SETTLEMENT_CODES = [880012 + i for i in range(CUSTOMER_COUNT)]
ACCOUNT_START = 100001
REF_MONTH = "202606"
MODEL_VERSION = "v3.2"
RECOVERY_RATES = [0.20, 0.40, 0.60]
INSTALLMENTS = [1, 2, 3]
SEGMENTS = ["Standard", "Premium", "Vulnerable", "Corporate", "3L"]
PRODUCTS = ["Personal Loan", "Credit Card", "Overdraft", "Auto Loan"]
CHANNELS = [
    ("Outbound Call", "Telephony"),
    ("Inbound Call", "Telephony"),
    ("SMS", "Digital"),
    ("Letter", "Mail"),
    ("Branch", "Face-to-Face"),
]
ACTIVITY_TYPES = [
    ("NFCT_RPC", "Phone", "Right party contact"),
    ("SMS", "SMS", "Message delivered"),
    ("LETTER", "Mail", "Letter sent"),
    ("NFCT_PTP", "Phone", "Promise to pay"),
    ("NO_CONTACT", "Phone", "No answer"),
]

SHAP_FEATURES = [
    ("Recent missed payments", -0.12),
    ("Long delinquency", -0.09),
    ("Low previous engagement", -0.07),
    ("High income stability", 0.11),
    ("Strong payment history", 0.08),
    ("Previous settlement acceptance", 0.06),
]

FIRST_NAMES = [
    "James", "Olivia", "Noah", "Emma", "Liam", "Ava", "William", "Sophia",
    "Oliver", "Isabella", "Benjamin", "Mia", "Lucas", "Charlotte", "Henry",
    "Amelia", "Alexander", "Harper", "Michael", "Evelyn", "Daniel", "Abigail",
    "Matthew", "Emily", "Samuel", "Elizabeth", "David", "Sofia", "Joseph", "Ella",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
]
COMPANY_NAMES = [
    "Northbridge Trading Ltd", "Aether Logistics PLC", "Summit Retail Group",
    "Cedar & Pine Holdings", "Blue Harbour Services Ltd", "Oakmont Capital Ltd",
    "Riverview Properties Ltd", "Sterling Works PLC", "Horizon Supply Co",
    "Meridian Facilities Ltd", "Brightpath Solutions Ltd", "Crownfield Partners",
    "Silverline Manufacturing", "Ashford Commercial Ltd", "Peninsula Foods Ltd",
    "Westgate Motors Ltd", "Lakeside Hospitality Ltd", "Ironwood Engineering",
    "Clearwater Media Ltd", "Fairmont Distribution PLC",
]

TRUNCATE_ORDER = [
    "fact_portfolio_kpis_monthly",
    "fact_shap_explanations",
    "fact_model_monitoring",
    "fact_efficient_frontier",
    "fact_offer_grid_scores",
    "fact_recommended_offers",
    "fact_activities",
    "fact_payments",
    "fact_applications",
    "bridge_settlement_customer_account",
    "fact_settlements_monthly",
    "fact_accounts_monthly",
    "dim_customer",
    "dim_region",
    "dim_channel",
    "dim_product",
    "dim_portfolio",
]


def legal_name_for(idx: int, segment: str) -> str:
    if segment == "Corporate":
        return COMPANY_NAMES[idx % len(COMPANY_NAMES)]
    return f"{FIRST_NAMES[idx % len(FIRST_NAMES)]} {LAST_NAMES[(idx * 7) % len(LAST_NAMES)]}"


def customer_profile(code: int) -> dict:
    idx = code - CUSTOMER_CODES[0]
    segment = SEGMENTS[idx % len(SEGMENTS)]
    is_corporate = segment == "Corporate"
    # Sparse production-like incidence (not pinned to demo IDs)
    flag_deceased = 1 if (not is_corporate and idx % 47 == 0) else 0
    flag_legal_entity = 1 if is_corporate else 0
    vulnerability = "Financial Hardship" if segment == "Vulnerable" and idx % 2 == 0 else "None"
    ood = idx % 53 == 0

    return {
        "customer_code": code,
        "legal_name": legal_name_for(idx, segment),
        "birth_date": date(1970 + (idx % 35), (idx % 12) + 1, (idx % 27) + 1),
        "age": 30 + (idx % 35),
        "flag_deceased": flag_deceased,
        "flag_legal_entity": flag_legal_entity,
        "flag_company_is_active": 1 if is_corporate else 1,
        "legal_entity_type": 1 if is_corporate else 0,
        "post_code": 10000 + (idx % 200),
        "nomos": ["Attica", "Thessaloniki", "Crete", "Patras"][idx % 4],
        "region": ["Athens", "North", "Islands", "West"][idx % 4],
        "occupation": "Director" if is_corporate else "Employee",
        "customer_type": "Corporate" if is_corporate else "Individual",
        "aml_risk": "Low" if idx % 4 else "Medium",
        "segment": segment,
        "flag_campaign": 1 if idx % 3 == 0 else 0,
        "flag_corporate": 1 if is_corporate else 0,
        "flag_legal": 0,
        "flag_under_law_protection": 1 if vulnerability != "None" and idx % 5 == 0 else 0,
        "vulnerability_status": vulnerability,
        "ood_flag": ood,
    }


def settlement_profile(code: int, customer_code: int, balance: float, n_accounts: int) -> dict:
    idx = customer_code - CUSTOMER_CODES[0]
    channel_name, channel_group = CHANNELS[idx % len(CHANNELS)]
    kept = round(0.45 + (idx % 5) * 0.04, 2)
    nr_inst = (idx % 3) + 1
    paid = round(balance * (0.08 + (idx % 5) * 0.01), 2)
    return {
        "settlement_code": code,
        "customer_code": customer_code,
        "ref_year_month": REF_MONTH,
        "reference_date": date(2026, 6, 30),
        "last_working_date": date(2026, 6, 30),
        "portfolio_name": "UK Retail Collections",
        "settlement_status": ["Active", "Active", "In Arrears", "Completed"][idx % 4],
        "settlement_status_date": date(2026, 5, 1) + timedelta(days=idx % 28),
        "settlement_created": date(2025, 11, 1) + timedelta(days=idx % 60),
        "settlement_activation_date": date(2025, 12, 1) + timedelta(days=idx % 40),
        "settlement_current_month": 3 + (idx % 8),
        "settlement_duration": 12 + (idx % 12),
        "settlement_nr_installments": nr_inst,
        "settlement_amount": round(balance * kept, 2),
        "settlement_principal_amount": round(balance * kept * 0.9, 2),
        "settlement_remaining_amount": round(balance * (1 - kept) + paid * 0.2, 2),
        "settlement_discount_amount": round(balance * (1 - kept), 2),
        "settlement_down_payment_amnt": round(balance * 0.05, 2),
        "settlement_kept_percentage": kept,
        "settlement_type_description": "Discounted Lump / Instalment",
        "settlement_arrears_days": (idx % 45) if idx % 4 == 2 else 0,
        "settlement_bucket": min(5, 1 + idx % 5),
        "settlement_arrears_amount": round(balance * 0.02, 2) if idx % 4 == 2 else 0.0,
        "settlement_paid_amount": paid,
        "past_installments_amnt": round(paid * 0.7, 2),
        "connected_loans": n_accounts,
        "total_balance_connected_loans": balance,
        "accounting_balance_connected_loans": round(balance * 0.98, 2),
        "written_off_amount_connected_loans": round(balance * 0.02, 2) if idx % 7 == 0 else 0.0,
        "principal_amount_connected_loans": round(balance * 0.85, 2),
        "assignment_channel_name": channel_name,
        "channel_group": channel_group,
        "payments_6m": round(balance * 0.08, 2),
        "latest_payment_date": date(2026, 5, 15) - timedelta(days=idx % 20),
        "days_from_last_activity": 3 + (idx % 25),
        "latest_activity_type": ACTIVITY_TYPES[idx % len(ACTIVITY_TYPES)][0],
        "latest_contact_type": ACTIVITY_TYPES[idx % len(ACTIVITY_TYPES)][1],
        "activity_days_3m": 4 + (idx % 10),
        "right_party_contact_activities_3m": 2 + (idx % 6),
        "nfct_rpc_activities_3m": 1 + (idx % 4),
        "sms_activities_3m": idx % 5,
    }


def grid_probs(customer_code: int, rr: float, inst: int) -> tuple[float, float, float]:
    return score_probabilities(customer_code, rr, inst)


SEED_USERS = [
    ("analyst@settlement.ai", "Alex Analyst", "analyst"),
    ("manager@settlement.ai", "Morgan Manager", "manager"),
    ("admin@settlement.ai", "Avery Admin", "admin"),
]
SEED_PASSWORD = "Settlement1!"


async def is_seeded(session: AsyncSession) -> bool:
    result = await session.execute(select(BridgeMapping).limit(1))
    return result.scalar_one_or_none() is not None


async def seed_users(session: AsyncSession) -> None:
    await session.execute(
        text(
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
            """
        )
    )
    hashed = hash_password(SEED_PASSWORD)
    for email, full_name, role in SEED_USERS:
        existing = (
            await session.execute(select(AppUser).where(AppUser.email == email))
        ).scalar_one_or_none()
        if existing:
            existing.full_name = full_name
            existing.role = role
            existing.hashed_password = hashed
            existing.is_active = True
        else:
            session.add(
                AppUser(
                    id=uuid4(),
                    email=email,
                    full_name=full_name,
                    hashed_password=hashed,
                    role=role,
                    is_active=True,
                )
            )
    # Deactivate legacy roles removed from the three-role model
    legacy_emails = ("stakeholder@settlement.ai", "compliance@settlement.ai")
    for email in legacy_emails:
        legacy = (
            await session.execute(select(AppUser).where(AppUser.email == email))
        ).scalar_one_or_none()
        if legacy:
            legacy.is_active = False
            legacy.role = "manager"
    await session.commit()
    print(f"Seeded {len(SEED_USERS)} app users (password: {SEED_PASSWORD}).")


async def clear_seed_tables(session: AsyncSession) -> None:
    await session.execute(text("SET session_replication_role = replica"))
    for table in TRUNCATE_ORDER:
        await session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    await session.execute(text("SET session_replication_role = origin"))
    await session.commit()


async def seed(session: AsyncSession) -> None:
    # Dimensions
    session.add_all(
        [
            DimRegion(post_code=10000 + i, nomos=n, region=r)
            for i, (n, r) in enumerate(
                [
                    ("Attica", "Athens"),
                    ("Thessaloniki", "North"),
                    ("Crete", "Islands"),
                    ("Patras", "West"),
                ]
            )
        ]
    )
    session.add_all([DimChannel(assignment_channel_name=n, channel_group=g) for n, g in CHANNELS])
    session.add_all(
        [
            DimProduct(business_unit="Retail", product=p)
            for p in PRODUCTS
        ]
        + [DimProduct(business_unit="Corporate", product="Business Loan")]
    )
    session.add_all(
        [
            DimPortfolio(portfolio_name="UK Retail Collections", portfolio_group="3L"),
            DimPortfolio(portfolio_name="UK SME Recoveries", portfolio_group="SME"),
        ]
    )
    await session.flush()

    customers: list[DimCustomer] = []
    settlements: list[FactSettlement] = []
    accounts: list[FactAccount] = []
    bridges: list[BridgeMapping] = []
    grids: list[FactOfferGridScore] = []
    recommendations: list[FactRecommendedOffer] = []
    shaps: list[FactShapExplanation] = []
    applications: list[FactApplication] = []
    payments: list[FactPayment] = []
    activities: list[FactActivity] = []

    account_code = ACCOUNT_START
    segment_ev: dict[str, float] = {s: 0.0 for s in SEGMENTS}
    segment_paid: dict[str, float] = {s: 0.0 for s in SEGMENTS}
    segment_count: dict[str, int] = {s: 0 for s in SEGMENTS}
    total_ev = 0.0
    total_paid = 0.0

    for i, customer_code in enumerate(CUSTOMER_CODES):
        settlement_code = SETTLEMENT_CODES[i]
        cp = customer_profile(customer_code)
        balance = round(2200 + (i * 185) + (i % 7) * 90 + (i % 11) * 35, 2)
        customers.append(DimCustomer(**cp))

        n_accounts = 2 if i % 3 == 0 else 1
        settlements.append(FactSettlement(**settlement_profile(settlement_code, customer_code, balance, n_accounts)))

        customer_accounts: list[int] = []
        for a_i in range(n_accounts):
            ac = account_code
            account_code += 1
            acc_balance = balance if n_accounts == 1 else round(balance / n_accounts, 2)
            channel_name, channel_group = CHANNELS[(i + a_i) % len(CHANNELS)]
            accounts.append(
                FactAccount(
                    account_code=ac,
                    customer_code=customer_code,
                    dpd=15 + (i % 90),
                    bucket=min(5, 1 + i % 5),
                    denouncement_amount=round(acc_balance * 0.1, 2) if i % 11 == 0 else 0.0,
                    debt_amount=acc_balance,
                    total_balance=acc_balance,
                    accounting_balance=round(acc_balance * 0.98, 2),
                    written_off_amount=round(acc_balance * 0.02, 2) if i % 9 == 0 else 0.0,
                    principal_amount=round(acc_balance * 0.85, 2),
                    interest_custom_type=["Fixed", "Variable"][i % 2],
                    account_open_date=date(2018, 1, 1) + timedelta(days=i * 40),
                    account_current_month=24 + (i % 48),
                    fixed_rate=0.045 + (i % 5) * 0.005,
                    total_interest_rate=0.06 + (i % 8) * 0.004,
                    spread=0.015,
                    assignment_channel_name=channel_name,
                    channel_group=channel_group,
                    business_unit="Retail" if cp["segment"] != "Corporate" else "Corporate",
                    product=PRODUCTS[i % len(PRODUCTS)],
                )
            )
            customer_accounts.append(ac)

        bridges.append(
            BridgeMapping(
                settlement_code=settlement_code,
                customer_code=customer_code,
                account_code=customer_accounts[0],
            )
        )

        best_ev = -1.0
        best_row: dict | None = None
        for rr in RECOVERY_RATES:
            for inst in INSTALLMENTS:
                p_app, p_accept, p_fulfill = grid_probs(customer_code, rr, inst)
                ev = compute_ev(balance, rr, p_app, p_accept, p_fulfill)
                grids.append(
                    FactOfferGridScore(
                        customer_code=customer_code,
                        settlement_code=settlement_code,
                        recovery_rate=rr,
                        installments=inst,
                        p_application=p_app,
                        p_acceptance=p_accept,
                        p_fulfillment=p_fulfill,
                        expected_value=ev,
                        model_version=MODEL_VERSION,
                        scored_at=date(2026, 6, 1),
                    )
                )
                if ev > best_ev:
                    best_ev = ev
                    best_row = {
                        "rr": rr,
                        "inst": inst,
                        "ev": ev,
                        "p_app": p_app,
                        "p_accept": p_accept,
                        "p_fulfill": p_fulfill,
                    }

        assert best_row is not None
        recommendations.append(
            FactRecommendedOffer(
                customer_code=customer_code,
                settlement_code=settlement_code,
                optimal_rr=best_row["rr"],
                optimal_installments=best_row["inst"],
                expected_value=best_row["ev"],
                mip_gap=0.0002,
                ref_year_month=REF_MONTH,
                model_version=MODEL_VERSION,
                p_application=best_row["p_app"],
                p_acceptance=best_row["p_accept"],
                p_fulfillment=best_row["p_fulfill"],
            )
        )

        seg = cp["segment"]
        segment_ev[seg] = segment_ev.get(seg, 0.0) + best_row["ev"]
        paid_amt = round(balance * (0.08 + (i % 5) * 0.01), 2)
        segment_paid[seg] = segment_paid.get(seg, 0.0) + paid_amt
        segment_count[seg] = segment_count.get(seg, 0) + 1
        total_ev += best_row["ev"]
        total_paid += paid_amt

        for fname, base_val in SHAP_FEATURES:
            shaps.append(
                FactShapExplanation(
                    customer_code=customer_code,
                    model_name="PoA_v3.1",
                    feature_name=fname,
                    shap_value=round(base_val + (i % 3) * 0.01, 4),
                    direction="positive" if base_val > 0 else "negative",
                    scored_at=date(2026, 6, 1),
                )
            )

        # Applications for ~60% of portfolio
        if i < 60:
            status = ["Submitted", "Approved", "In Review", "Implemented", "Rejected"][i % 5]
            stage = ["Assessment", "QC", "Implementation", "Activation", "Closed"][i % 5]
            applications.append(
                FactApplication(
                    application_code=500001 + i,
                    customer_code=customer_code,
                    customer_id=customer_code,
                    settlement_code=settlement_code,
                    portfolio="UK Retail Collections",
                    portfolio_group="3L",
                    customer_segment=seg,
                    application_status=status,
                    pipeline_status=stage,
                    qc_application_status="Passed" if status != "Rejected" else "Failed",
                    current_stage=stage,
                    current_stage_start_date=date(2026, 4, 1) + timedelta(days=i),
                    current_step=stage,
                    start_date=date(2026, 3, 1) + timedelta(days=i),
                    creation_date=date(2026, 3, 1) + timedelta(days=i),
                    submission_date=date(2026, 3, 5) + timedelta(days=i),
                    approval_date=date(2026, 3, 20) + timedelta(days=i) if status in ("Approved", "Implemented") else None,
                    assignment_channel=CHANNELS[i % len(CHANNELS)][0],
                    application_channel=CHANNELS[(i + 1) % len(CHANNELS)][0],
                    assigned_officer=f"Officer {(i % 8) + 1}",
                    initial_tenor=best_row["inst"],
                    initial_installment_amount=round(balance * best_row["rr"] / max(best_row["inst"], 1), 2),
                    final_tenor=best_row["inst"],
                    final_installment_amount=round(balance * best_row["rr"] / max(best_row["inst"], 1), 2),
                    final_solution_type="Settlement",
                    settlement_amount=round(balance * best_row["rr"], 2),
                    flag_law=1 if cp.get("flag_under_law_protection") else 0,
                )
            )

        for m in range(6):
            payments.append(
                FactPayment(
                    customer_code=customer_code,
                    payment_date=date(2026, 1, 10) + timedelta(days=m * 30 + (i % 5)),
                    payment_amount=round(balance * (0.012 + (m % 3) * 0.002), 2),
                    payment_type=["Partial", "Instalment", "Lump"][m % 3],
                )
            )

        for a_i in range(3 + (i % 3)):
            atype, ctype, outcome = ACTIVITY_TYPES[(i + a_i) % len(ACTIVITY_TYPES)]
            activities.append(
                FactActivity(
                    customer_code=customer_code,
                    settlement_code=settlement_code,
                    activity_date=date(2026, 4, 1) + timedelta(days=a_i * 7 + (i % 4)),
                    activity_type=atype,
                    contact_type=ctype,
                    outcome=outcome,
                )
            )

    # Portfolio KPI monthly snapshots (All + segments)
    months = ["202601", "202602", "202603", "202604", "202605", "202606"]
    kpis: list[FactPortfolioKpiMonthly] = []
    for mi, month in enumerate(months):
        factor = 0.88 + mi * 0.024
        real = 0.38 + mi * 0.01
        kpis.append(
            FactPortfolioKpiMonthly(
                ref_year_month=month,
                segment="All",
                expected_value=round(total_ev * factor, 2),
                actual_collections=round(total_paid * factor * 1.05, 2),
                realization_rate=round(real, 4),
                borrower_count=CUSTOMER_COUNT,
            )
        )
        for seg in SEGMENTS:
            sev = segment_ev.get(seg, 0.0)
            spaid = segment_paid.get(seg, 0.0)
            if sev <= 0:
                continue
            kpis.append(
                FactPortfolioKpiMonthly(
                    ref_year_month=month,
                    segment=seg,
                    expected_value=round(sev * factor, 2),
                    actual_collections=round(spaid * factor * 1.05, 2),
                    realization_rate=round(real + (hash(seg) % 5) * 0.002, 4),
                    borrower_count=segment_count.get(seg, 0),
                )
            )

    # Dense efficient frontier (~10 points)
    frontier_defs = [
        ("Ultra Conservative", 4_200_000, "Low", 0.15, 0.85, 0.30),
        ("Conservative", 5_000_000, "Low", 0.25, 0.80, 0.40),
        ("Defensive", 5_800_000, "Low", 0.32, 0.78, 0.45),
        ("Balanced-", 6_400_000, "Medium", 0.42, 0.74, 0.50),
        ("Balanced", 7_000_000, "Medium", 0.50, 0.70, 0.60),
        ("Balanced+", 7_500_000, "Medium", 0.58, 0.68, 0.65),
        ("Growth", 8_000_000, "High", 0.66, 0.64, 0.70),
        ("Aggressive", 8_500_000, "High", 0.75, 0.60, 0.80),
        ("Max EV", 9_100_000, "High", 0.82, 0.55, 0.85),
        ("Frontier Edge", 9_400_000, "High", 0.88, 0.50, 0.90),
    ]
    frontier = [
        FactEfficientFrontier(
            strategy_name=name,
            portfolio_ev=ev,
            risk_level=risk,
            risk_score=score,
            min_p_fulfill=min_pf,
            max_rr=max_rr,
            ref_year_month=REF_MONTH,
        )
        for name, ev, risk, score, min_pf, max_rr in frontier_defs
    ]

    monitoring: list[FactModelMonitoring] = []
    for model in ["PoAPP", "PoA", "PoF"]:
        for metric, val, base, alert in [
            ("PSI", 0.08 if model != "PoA" else 0.14, 0.10, model == "PoA"),
            ("drift", 0.09 if model != "PoAPP" else 0.13, 0.10, model == "PoAPP"),
            ("calibration", 0.94, 0.95, False),
            ("stability", 0.97, 0.95, False),
        ]:
            monitoring.append(
                FactModelMonitoring(
                    model_name=model,
                    metric_name=metric,
                    metric_value=val,
                    baseline_value=base,
                    ref_year_month=REF_MONTH,
                    alert_flag=alert,
                )
            )

    session.add_all(customers)
    await session.flush()
    session.add_all(accounts)
    await session.flush()
    session.add_all(settlements)
    await session.flush()
    session.add_all(bridges)
    await session.flush()
    session.add_all(grids)
    session.add_all(recommendations)
    session.add_all(shaps)
    session.add_all(applications)
    session.add_all(payments)
    session.add_all(activities)
    session.add_all(kpis)
    session.add_all(frontier)
    session.add_all(monitoring)
    await session.commit()
    print(
        f"Seeded {CUSTOMER_COUNT} borrowers, {len(accounts)} accounts, "
        f"{len(grids)} offer rows, {len(applications)} applications, {len(kpis)} KPI snapshots."
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed settlement portfolio demo data")
    parser.add_argument("--force", action="store_true", help="Truncate and reseed")
    args = parser.parse_args()

    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Ensure schema patches exist on older volumes (asyncpg: one statement per execute)
    async with engine.begin() as conn:
        await conn.execute(
            text(
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
                """
            )
        )
        await conn.execute(
            text("ALTER TABLE dim_customer ADD COLUMN IF NOT EXISTS legal_name VARCHAR(200)")
        )

    for attempt in range(30):
        try:
            async with session_factory() as session:
                if args.force:
                    print("Force reseed: clearing seed tables...")
                    await clear_seed_tables(session)
                    await seed(session)
                    print("Database seeded successfully.")
                elif await is_seeded(session):
                    print("Database already seeded, skipping portfolio seed. Use --force to reseed.")
                else:
                    await seed(session)
                    print("Database seeded successfully.")
                await seed_users(session)
                return
        except Exception as exc:
            print(f"Seed attempt {attempt + 1} failed: {exc}")
            await asyncio.sleep(2)
    raise RuntimeError("Failed to seed database after retries")


if __name__ == "__main__":
    asyncio.run(main())
