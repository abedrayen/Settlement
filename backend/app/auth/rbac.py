from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

VALID_ROLES = {"analyst", "manager", "admin"}

# Legacy roles map onto manager (Operational Manager absorbs stakeholder/compliance).
_LEGACY_ROLE_MAP = {
    "stakeholder": "manager",
    "compliance": "manager",
    "executive": "manager",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "analyst": {
        "chat",
        "borrower",
        "strategy_read",
        "documents_read",
    },
    "manager": {
        "chat",
        "borrower",
        "portfolio_read",
        "strategy_read",
        "strategy_run",
        "workflows",
        "workflows_approve",
        "audit_read",
        "audit_export",
        "documents_read",
        "executive_read",
        "monitoring_read",
    },
    "admin": {
        "chat",
        "borrower",
        "portfolio_read",
        "strategy_read",
        "strategy_run",
        "workflows",
        "workflows_approve",
        "audit_read",
        "audit_export",
        "settings_read",
        "settings_write",
        "documents_read",
        "executive_read",
        "monitoring_read",
    },
}

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str
    role: str
    full_name: str | None = None


def normalize_role(role: str | None) -> str:
    r = (role or "analyst").lower()
    r = _LEGACY_ROLE_MAP.get(r, r)
    return r if r in VALID_ROLES else "analyst"


def require_permission(role: str, permission: str) -> None:
    normalized = normalize_role(role)
    if permission not in ROLE_PERMISSIONS.get(normalized, set()):
        raise HTTPException(403, f"Role '{normalized}' cannot access this resource")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    from app.auth.security import decode_access_token

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(401, "Invalid or expired token") from None

    sub = payload.get("sub")
    email = payload.get("email")
    role = normalize_role(payload.get("role"))
    if not sub or not email:
        raise HTTPException(401, "Invalid token payload")
    try:
        user_id = UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(401, "Invalid token subject") from exc

    return CurrentUser(id=user_id, email=str(email), role=role, full_name=payload.get("full_name"))


async def get_role(user: Annotated[CurrentUser, Depends(get_current_user)]) -> str:
    return user.role
