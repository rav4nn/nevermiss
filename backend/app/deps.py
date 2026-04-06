from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError, ErrorCode
from app.core.jwt import decode_nextauth_token
from app.models.user import User


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency that authenticates every protected request.

    Extracts the Bearer JWT issued by NextAuth, verifies it with the shared
    NEXTAUTH_SECRET (HS256), resolves the `sub` claim to a users row, and
    returns the User ORM object.

    Raises AppError(UNAUTHENTICATED, 401) for any of:
    - Missing or malformed Authorization header
    - Invalid, expired, or tampered token
    - `sub` claim is not a valid UUID
    - User not found in the database
    - User account has been soft-deleted (deleted_at is set)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Missing or invalid Authorization header.",
            status_code=401,
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Missing or invalid Authorization header.",
            status_code=401,
        )

    settings = get_settings()
    # decode_nextauth_token raises AppError(UNAUTHENTICATED) on any JWT failure.
    # We do NOT log the raw token value here or anywhere in this call path.
    payload = decode_nextauth_token(token, settings.nextauth_secret)

    raw_sub = payload.get("sub")
    if not isinstance(raw_sub, str) or not raw_sub:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Invalid token: missing sub claim.",
            status_code=401,
        )

    try:
        user_id = uuid.UUID(raw_sub)
    except ValueError:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "Invalid token: malformed sub claim.",
            status_code=401,
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or user.deleted_at is not None:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "User not found.",
            status_code=401,
        )

    return user


# Reusable annotated dependency for route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
