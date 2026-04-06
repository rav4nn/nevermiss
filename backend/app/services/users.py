from __future__ import annotations

import asyncio
from urllib import error, parse, request

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.user import SessionCreateRequest

logger = get_logger("app.services.users")


async def _get_user_by_google_sub(session: AsyncSession, google_sub: str) -> User | None:
    result = await session.execute(select(User).where(User.google_sub == google_sub))
    return result.scalar_one_or_none()


async def create_or_update_user_session(
    session: AsyncSession,
    payload: SessionCreateRequest,
) -> User:
    user = await _get_user_by_google_sub(session, payload.google_sub)
    encrypted_refresh_token = crypto.encrypt(payload.refresh_token)
    encrypted_access_token = crypto.encrypt(payload.access_token)

    if user is None:
        user = User(
            email=payload.email,
            gmail_address=payload.gmail_address,
            google_sub=payload.google_sub,
            refresh_token_enc=encrypted_refresh_token,
            access_token_enc=encrypted_access_token,
            access_token_expires_at=payload.access_token_expires_at,
            timezone=payload.timezone,
        )
        session.add(user)
    else:
        user.email = payload.email
        user.gmail_address = payload.gmail_address
        user.refresh_token_enc = encrypted_refresh_token
        user.access_token_enc = encrypted_access_token
        user.access_token_expires_at = payload.access_token_expires_at
        user.timezone = payload.timezone

    await session.commit()
    await session.refresh(user)
    return user


def _revoke_google_refresh_token(refresh_token: str) -> None:
    revoke_url = "https://oauth2.googleapis.com/revoke?token=" + parse.quote(refresh_token, safe="")
    req = request.Request(revoke_url, data=b"", method="POST")
    with request.urlopen(req, timeout=10) as response:
        if response.status < 200 or response.status >= 300:
            raise error.HTTPError(
                revoke_url,
                response.status,
                "Google token revoke failed.",
                response.headers,
                None,
            )


async def delete_user(session: AsyncSession, user: User) -> None:
    try:
        refresh_token = crypto.decrypt(user.refresh_token_enc)
    except crypto.CryptoError:
        logger.warning("google_revoke_skipped_due_to_decrypt_failure", user_id=str(user.id))
    else:
        try:
            await asyncio.to_thread(_revoke_google_refresh_token, refresh_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "google_revoke_failed",
                user_id=str(user.id),
                error_type=type(exc).__name__,
            )

    session.add(AuditLog(user_id=user.id, event="user_deleted", payload={}))
    await session.flush()
    await session.delete(user)
    await session.commit()
