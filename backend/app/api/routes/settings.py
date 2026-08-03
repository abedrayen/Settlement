from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.rbac import get_role, require_permission
from app.services.settings_store import (
    get_data_freshness,
    get_model_versions,
    load_guardrail_config,
    save_guardrail_config,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class GuardrailConfigUpdate(BaseModel):
    rr_min: float = Field(ge=0, le=1)
    rr_max: float = Field(ge=0, le=1)
    flags: dict[str, bool] = Field(default_factory=dict)


@router.get("/freshness")
async def data_freshness(role: str = Depends(get_role)) -> dict[str, Any]:
    require_permission(role, "chat")
    return get_data_freshness()


@router.get("/models")
async def model_versions(role: str = Depends(get_role)) -> list[dict[str, Any]]:
    require_permission(role, "settings_read")
    return get_model_versions()


@router.get("/guardrails")
async def get_guardrails(role: str = Depends(get_role)) -> dict[str, Any]:
    require_permission(role, "settings_read")
    return load_guardrail_config()


@router.put("/guardrails")
async def update_guardrails(body: GuardrailConfigUpdate, role: str = Depends(get_role)) -> dict[str, Any]:
    require_permission(role, "settings_write")
    if body.rr_min >= body.rr_max:
        raise HTTPException(400, "rr_min must be less than rr_max")
    config = {"rr_min": body.rr_min, "rr_max": body.rr_max, "flags": body.flags}
    return save_guardrail_config(config)
