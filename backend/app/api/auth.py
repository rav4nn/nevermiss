from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.user import SessionCreateRequest, UserResponse
from app.services.users import create_or_update_user_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/session", response_model=UserResponse)
async def create_session(
    payload: SessionCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    user = await create_or_update_user_session(db, payload)
    return UserResponse.model_validate(user)
