from __future__ import annotations

from sqlalchemy import select

from app.core.db import ScanKind, ScanStatus, UserTier, get_db
from app.core.logging import get_logger
from app.models.scan_job import ScanJob
from app.models.user import User

logger = get_logger("workers.weekly_cron")


async def enqueue_all_pro_users() -> None:
    async for session in get_db():
        result = await session.execute(
            select(User).where(
                User.tier == UserTier.PRO,
                User.deleted_at.is_(None),
            )
        )
        users = result.scalars().all()

        for user in users:
            active_result = await session.execute(
                select(ScanJob).where(
                    ScanJob.user_id == user.id,
                    ScanJob.status.in_((ScanStatus.QUEUED, ScanStatus.RUNNING)),
                )
            )
            if active_result.scalar_one_or_none() is not None:
                continue

            session.add(
                ScanJob(
                    user_id=user.id,
                    kind=ScanKind.WEEKLY,
                    status=ScanStatus.QUEUED,
                )
            )

        await session.commit()
        logger.info("weekly_scan_enqueue_complete", user_count=len(users))
        return
