from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CurrentUser, get_current_user
from app.auth.security import create_access_token, verify_password
from app.database import get_db
from app.models.entities import AppUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _user_out(user: AppUser) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    email = body.email.strip().lower()
    result = await db.execute(select(AppUser).where(AppUser.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return LoginResponse(access_token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
async def me(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    result = await db.execute(select(AppUser).where(AppUser.id == current.id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(401, "User not found")
    return _user_out(user)


@router.post("/logout")
async def logout() -> dict[str, str]:
    return {"status": "ok"}
