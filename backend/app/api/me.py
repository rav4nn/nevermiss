from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser
from app.schemas.user import UserResponse
from app.services.users import delete_user

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await delete_user(db, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
