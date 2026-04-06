from __future__ import annotations

import hashlib
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dismissed_signature import DismissedSignature


def compute_signature(name: str, category: str, expiry_date: date) -> str:
    payload = f"{name.lower()}|{category}|{expiry_date.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _get_dismissed_signature(
    session: AsyncSession,
    user_id: uuid.UUID,
    signature: str,
) -> DismissedSignature | None:
    statement = select(DismissedSignature).where(
        DismissedSignature.user_id == user_id,
        DismissedSignature.signature == signature,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def is_dismissed(
    session: AsyncSession,
    user_id: uuid.UUID,
    signature: str,
) -> bool:
    return await _get_dismissed_signature(session, user_id, signature) is not None


async def add_dismissed(
    session: AsyncSession,
    user_id: uuid.UUID,
    signature: str,
) -> None:
    existing = await _get_dismissed_signature(session, user_id, signature)
    if existing is not None:
        return

    session.add(DismissedSignature(user_id=user_id, signature=signature))
    await session.flush()


async def remove_dismissed(
    session: AsyncSession,
    user_id: uuid.UUID,
    signature: str,
) -> None:
    dismissed_signature = await _get_dismissed_signature(session, user_id, signature)
    if dismissed_signature is None:
        return

    await session.delete(dismissed_signature)
    await session.flush()
