from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy import select

from app import __version__
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger, setup_logging
from app.integrations.gmail import GmailReauthRequired, build_gmail_service
from app.models.user import User
from app.workers import digest_cron, scan_runner, weekly_cron

logger = get_logger("main_worker")


async def refresh_token_sweeper() -> None:
    now = datetime.now(UTC)
    threshold = now + timedelta(hours=1)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.deleted_at.is_(None),
                User.refresh_token_enc.is_not(None),
                User.access_token_expires_at.is_not(None),
                User.access_token_expires_at < threshold,
            )
        )
        users = result.scalars().all()

        refreshed = 0
        for user in users:
            try:
                service = build_gmail_service(
                    user.refresh_token_enc,
                    user.access_token_enc,
                    user.access_token_expires_at,
                )
            except GmailReauthRequired:
                user.refresh_token_enc = None
                continue

            token_state = getattr(service, "_nevermiss_token_state", {})
            access_token_enc = token_state.get("access_token_enc")
            access_token_expires_at = token_state.get("access_token_expires_at")
            if access_token_enc:
                user.access_token_enc = access_token_enc
                user.access_token_expires_at = access_token_expires_at
                refreshed += 1

        await session.commit()
        logger.info("refresh_token_sweeper_complete", user_count=len(users), refreshed=refreshed)


def _safe_job(
    name: str,
    handler: Callable[[], Awaitable[None]],
) -> Callable[[], Awaitable[None]]:
    async def _runner() -> None:
        try:
            await handler()
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker_job_failed", job_name=name, error_type=type(exc).__name__)

    return _runner


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _safe_job("poll_scan_jobs", scan_runner.process_next_job),
        trigger="interval",
        seconds=5,
        id="poll_scan_jobs",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _safe_job("weekly_scan_enqueue", weekly_cron.enqueue_all_pro_users),
        trigger="cron",
        day_of_week="sun",
        hour=2,
        minute=0,
        id="weekly_scan_enqueue",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _safe_job("weekly_digest_send", digest_cron.send_due_digests),
        trigger="cron",
        minute=0,
        id="weekly_digest_send",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _safe_job("refresh_token_sweeper", refresh_token_sweeper),
        trigger="cron",
        minute="*/30",
        id="refresh_token_sweeper",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    scheduler = create_scheduler()
    app.state.scheduler = scheduler
    scheduler.start()
    logger.info("worker_scheduler_started")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("worker_scheduler_stopped")


def create_app() -> FastAPI:
    return FastAPI(title="NeverMiss Worker", version=__version__, lifespan=lifespan)


app = create_app()
