from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import ScanKind, ScanStatus
from app.core.errors import AppError, ErrorCode
from app.models.scan_job import ScanJob
from app.models.user import User
from app.schemas.scan import ScanStartRequest
from app.services.rate_limit import check_rate_limit
from app.services.tier import require_pro


async def _get_active_scan_for_user(session: AsyncSession, user: User) -> ScanJob | None:
    result = await session.execute(
        select(ScanJob).where(
            ScanJob.user_id == user.id,
            ScanJob.status.in_((ScanStatus.QUEUED, ScanStatus.RUNNING)),
        )
    )
    return result.scalar_one_or_none()


async def enqueue_scan(
    session: AsyncSession,
    user: User,
    payload: ScanStartRequest,
) -> ScanJob:
    check_rate_limit(f"scan:start:{user.id}", limit=3, window_seconds=3600)

    active_job = await _get_active_scan_for_user(session, user)
    if active_job is not None:
        raise AppError(
            ErrorCode.SCAN_IN_PROGRESS,
            "A scan is already queued or running.",
            status_code=409,
        )

    if not user.refresh_token_enc:
        raise AppError(
            ErrorCode.GMAIL_REAUTH_REQUIRED,
            "Google account re-authorization is required.",
            status_code=400,
        )

    if payload.kind == ScanKind.MANUAL:
        require_pro(user)

    job = ScanJob(
        user_id=user.id,
        kind=payload.kind,
        status=ScanStatus.QUEUED,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_latest_scan(session: AsyncSession, user: User) -> ScanJob:
    result = await session.execute(
        select(ScanJob)
        .where(ScanJob.user_id == user.id)
        .order_by(ScanJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise AppError(
            ErrorCode.NOT_FOUND,
            "No scan job found.",
            status_code=404,
        )
    return job
