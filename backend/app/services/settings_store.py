from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[2] / "content" / "guardrail_config.json"

DATA_SOURCES = [
    {
        "source_id": "settlements",
        "name": "Settlement Ledger",
        "cadence": "monthly",
        "last_refresh": "2026-06-15T08:00:00Z",
        "ref_year_month": "202606",
    },
    {
        "source_id": "offer_grid",
        "name": "Offer Grid Scores",
        "cadence": "weekly",
        "last_refresh": "2026-06-14T02:30:00Z",
        "ref_year_month": "202606",
    },
    {
        "source_id": "models",
        "name": "PoAPP / PoA / PoF Bundle",
        "cadence": "quarterly",
        "last_refresh": "2026-04-01T00:00:00Z",
        "ref_year_month": "202606",
    },
]

MODEL_VERSIONS = [
    {
        "bundle": "PoAPP/PoA/PoF/RSF",
        "version": "v3.2",
        "retrain_date": "2026-04-01",
        "active": True,
        "components": {"PoAPP": "v3.2", "PoA": "v3.1", "PoF": "v3.2", "RSF": "v1.0"},
    },
    {
        "bundle": "PoAPP/PoA/PoF/RSF",
        "version": "v3.1",
        "retrain_date": "2025-12-15",
        "active": False,
        "components": {"PoAPP": "v3.1", "PoA": "v3.0", "PoF": "v3.1", "RSF": "v1.0"},
    },
]


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_guardrail_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"rr_min": 0.2, "rr_max": 0.8, "flags": {}}


def save_guardrail_config(config: dict[str, Any]) -> dict[str, Any]:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def get_data_freshness() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    sources = []
    for src in DATA_SOURCES:
        last = _parse_iso(src["last_refresh"])
        days = (now - last).days
        cadence_days = {"real-time": 1, "weekly": 7, "monthly": 31, "quarterly": 92}.get(src["cadence"], 31)
        sources.append({**src, "days_since_refresh": days, "stale": days > cadence_days})
    return {
        "ref_year_month": "202606",
        "as_of": "June 2026",
        "last_refresh_display": "15 Jun 2026, 08:00 UTC",
        "sources": sources,
    }


def get_model_versions() -> list[dict[str, Any]]:
    return MODEL_VERSIONS
