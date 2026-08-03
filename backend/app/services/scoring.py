"""Shared three-stage probability chain and Expected Value math.

Used by seed_db and runtime ModelScorer so demo scores stay identical.
"""
from __future__ import annotations


def score_probabilities(
    customer_code: int,
    rr: float,
    installments: int,
    segment_factor: float = 0.0,
) -> tuple[float, float, float]:
    """Return (PoAPP, PoA, PoF) for a borrower/offer pair.

    Deterministic simulated scoring — not live model inference.
    """
    base = 0.48 + (customer_code % 12) * 0.015 + segment_factor
    p_app = min(0.95, max(0.35, base + 0.18 - rr * 0.12))
    p_accept = min(0.90, max(0.30, base + 0.12 - installments * 0.04))
    p_fulfill = min(0.92, max(0.40, base + 0.22 - rr * 0.06 + installments * 0.015))
    return round(p_app, 4), round(p_accept, 4), round(p_fulfill, 4)


def compute_ev(balance: float, rr: float, p_app: float, p_accept: float, p_fulfill: float) -> float:
    """EV = PoAPP × PoA × PoF × Settlement Amount."""
    return round(p_app * p_accept * p_fulfill * (balance * rr), 2)


def score_offer(
    customer_code: int,
    balance: float,
    rr: float,
    installments: int,
    segment_factor: float = 0.0,
) -> dict[str, float]:
    p_app, p_accept, p_fulfill = score_probabilities(customer_code, rr, installments, segment_factor)
    ev = compute_ev(balance, rr, p_app, p_accept, p_fulfill)
    return {
        "p_application": p_app,
        "p_acceptance": p_accept,
        "p_fulfillment": p_fulfill,
        "recovery_rate": rr,
        "installments": float(installments),
        "settlement_amount": round(balance * rr, 2),
        "expected_value": ev,
    }


# Aliases matching seed_db historical names
grid_probs = score_probabilities
