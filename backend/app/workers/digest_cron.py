from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select

from app.core.db import UserTier, get_db
from app.core.logging import get_logger
from app.integrations.resend_client import send_email
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.items import get_items

logger = get_logger("workers.digest_cron")
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _is_digest_window(user: User, now_utc: datetime) -> bool:
    local_now = now_utc.astimezone(ZoneInfo(user.timezone))
    return local_now.weekday() == 0 and local_now.hour == 8


async def _sent_digest_recently(session, user_id, now_utc: datetime) -> bool:
    cutoff = now_utc - timedelta(hours=23)
    result = await session.execute(
        select(AuditLog).where(
            AuditLog.user_id == user_id,
            AuditLog.event == "digest_sent",
            AuditLog.created_at >= cutoff,
        )
    )
    return result.scalar_one_or_none() is not None


def _subject_line(critical_count: int, urgent_count: int, soon_count: int) -> str:
    expiring_this_week = critical_count + urgent_count
    return (
        f"NeverMiss — {expiring_this_week} things expiring this week, "
        f"{soon_count} coming up soon"
    )


async def send_due_digests() -> None:
    now_utc = _now_utc()

    async for session in get_db():
        result = await session.execute(
            select(User).where(
                User.tier == UserTier.PRO,
                User.deleted_at.is_(None),
            )
        )
        users = result.scalars().all()

        for user in users:
            try:
                if not _is_digest_window(user, now_utc):
                    continue
                if await _sent_digest_recently(session, user.id, now_utc):
                    continue

                critical = await get_items(
                    session,
                    user,
                    dismissed=False,
                    urgency={"critical"},
                    limit=500,
                    offset=0,
                )
                urgent = await get_items(
                    session,
                    user,
                    dismissed=False,
                    urgency={"urgent"},
                    limit=500,
                    offset=0,
                )
                soon = await get_items(
                    session,
                    user,
                    dismissed=False,
                    urgency={"soon"},
                    limit=500,
                    offset=0,
                )

                context = {
                    "user": user,
                    "critical_items": critical["items"],
                    "urgent_items": urgent["items"],
                    "soon_items": soon["items"],
                }
                html = jinja_env.get_template("digest_html.j2").render(**context)
                text = jinja_env.get_template("digest_plain.j2").render(**context)
                subject = _subject_line(
                    len(critical["items"]),
                    len(urgent["items"]),
                    len(soon["items"]),
                )
                send_email(user.email, subject, html, text)
                session.add(AuditLog(user_id=user.id, event="digest_sent", payload={}))
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                logger.error(
                    "digest_send_failed",
                    user_id=str(user.id),
                    error_type=type(exc).__name__,
                )
                continue

        logger.info("weekly_digest_send_complete", user_count=len(users))
        return
