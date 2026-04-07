from __future__ import annotations

import asyncio
import socket
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, ScanKind, ScanStatus, UserTier
from app.core.logging import bind_log_context, clear_log_context, get_logger
from app.integrations import gemini, gmail
from app.integrations.gmail import GmailReauthRequired
from app.models.item import ExtractedItem
from app.models.scan_job import ScanJob
from app.models.user import User
from app.services import signatures

logger = get_logger("workers.scan_runner")

# Max concurrent Gmail message fetches within a single batch.
# httplib2 and googleapiclient Resources are NOT thread-safe; run fetches sequentially.
_FETCH_SEMAPHORE = asyncio.Semaphore(1)

# Max concurrent scan jobs across the whole worker process.
_JOB_SEMAPHORE = asyncio.Semaphore(3)

# Unique identifier for this worker instance (used for locked_by).
_WORKER_ID = socket.gethostname()


def _since_date(job: ScanJob, user: User) -> date:
    """
    Determine the email history start date for this scan.

    free  + initial  -> 90 days back
    pro   + initial  -> 400 days back
    any   + weekly   -> user.last_scan_at date (falls back to 7 days if null)
    any   + manual   -> 90 days back
    """
    today = datetime.now(UTC).date()
    if job.kind == ScanKind.WEEKLY:
        if user.last_scan_at is not None:
            return user.last_scan_at.astimezone(UTC).date()
        return today - timedelta(days=7)
    if job.kind == ScanKind.INITIAL:
        days = 400 if user.tier == UserTier.PRO else 90
        return today - timedelta(days=days)
    # manual
    return today - timedelta(days=90)


async def _fetch_body(
    service: object,
    message_id: str,
) -> tuple[str, str, datetime] | None:
    """Fetch a single message body, returning None on error."""
    async with _FETCH_SEMAPHORE:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, gmail.get_message_body, service, message_id
            )
            return result
        except Exception as exc:
            logger.warning("gmail_fetch_message_failed", message_id=message_id, error=str(exc))
            return None


async def _process_batch(
    db: AsyncSession,
    user: User,
    service: object,
    message_ids: list[str],
) -> int:
    """
    Fetch bodies and run extraction for one batch of message IDs.
    Returns the count of newly inserted items.
    """
    fetch_tasks = [_fetch_body(service, mid) for mid in message_ids]
    fetch_results = await asyncio.gather(*fetch_tasks)

    items_inserted = 0

    for message_id, fetch_result in zip(message_ids, fetch_results):
        if fetch_result is None:
            continue

        body, sender, sent_at = fetch_result

        # Gemini is synchronous — run in thread pool executor.
        try:
            extractions = await asyncio.get_event_loop().run_in_executor(
                None, gemini.extract_items, body, sender, sent_at, user
            )
        except Exception as exc:
            logger.warning(
                "gemini_extraction_failed",
                message_id=message_id,
                error=str(exc),
            )
            extractions = []
        finally:
            # Spec rule 3: email body must not persist beyond this point.
            del body

        for extraction in extractions:
            sig = signatures.compute_signature(
                extraction.name,
                extraction.category.value,
                extraction.date,
            )
            if await signatures.is_dismissed(db, user.id, sig):
                continue

            # ON CONFLICT DO NOTHING — idempotent across retries and re-scans.
            stmt = (
                pg_insert(ExtractedItem)
                .values(
                    user_id=user.id,
                    name=extraction.name,
                    category=extraction.category,
                    expiry_date=extraction.date,
                    date_type=extraction.date_type,
                    confidence=extraction.confidence,
                    notes=extraction.notes or None,
                    source_sender=sender,
                    source_date=sent_at,
                    source_message_id=message_id,
                )
                .on_conflict_do_nothing(constraint="uq_user_msg_name")
            )
            proxy = await db.execute(stmt)
            if proxy.rowcount > 0:
                items_inserted += 1

        del extractions

    return items_inserted


async def _handle_reauth(db: AsyncSession, user: User, job: ScanJob) -> None:
    """
    Clear the stored refresh token and fail the job.
    Frontend detects GMAIL_REAUTH_REQUIRED error and shows re-auth banner.
    """
    logger.warning("scan_job_gmail_reauth_required", user_id=str(user.id))
    await db.execute(
        update(User).where(User.id == user.id).values(refresh_token_enc=None)
    )
    await _fail_job(db, job, "GMAIL_REAUTH_REQUIRED")


async def _fail_job(db: AsyncSession, job: ScanJob, error: str) -> None:
    await db.execute(
        update(ScanJob)
        .where(ScanJob.id == job.id)
        .values(
            status=ScanStatus.FAILED,
            completed_at=datetime.now(UTC),
            error=error,
        )
    )
    await db.commit()
    logger.warning("scan_job_failed", job_id=str(job.id), error=error)


async def _run_job(db: AsyncSession, job: ScanJob) -> None:
    """Execute a single scan job end-to-end."""
    bind_log_context(user_id=str(job.user_id), job_id=str(job.id))
    logger.info("scan_job_started", kind=job.kind)

    user_result = await db.execute(select(User).where(User.id == job.user_id))
    user: User | None = user_result.scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        await _fail_job(db, job, "User not found or deleted.")
        return

    # Build Gmail service (sync Google auth call — run in executor).
    try:
        service = await asyncio.get_event_loop().run_in_executor(
            None,
            gmail.build_gmail_service,
            user.refresh_token_enc,
            user.access_token_enc,
            user.access_token_expires_at,
        )
    except GmailReauthRequired:
        await _handle_reauth(db, user, job)
        return
    except Exception as exc:
        logger.error("scan_job_gmail_build_failed", error=str(exc))
        await _fail_job(db, job, f"Gmail service error: {exc}")
        return

    # If token was refreshed, persist the new encrypted access token.
    token_state: dict = getattr(service, "_nevermiss_token_state", {})
    if token_state.get("access_token_enc"):
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(
                access_token_enc=token_state["access_token_enc"],
                access_token_expires_at=token_state.get("access_token_expires_at"),
            )
        )
        await db.flush()

    # Determine scan window and collect all message IDs.
    since = _since_date(job, user)
    logger.info("scan_job_listing_messages", since=since.isoformat())

    try:
        message_ids: list[str] = await asyncio.get_event_loop().run_in_executor(
            None, gmail.list_message_ids, service, since
        )
    except GmailReauthRequired:
        await _handle_reauth(db, user, job)
        return
    except Exception as exc:
        logger.error("scan_job_list_messages_failed", error=str(exc))
        await _fail_job(db, job, f"Failed to list Gmail messages: {exc}")
        return

    emails_total = len(message_ids)
    await db.execute(
        update(ScanJob).where(ScanJob.id == job.id).values(emails_total=emails_total)
    )
    await db.commit()  # commit so the UI immediately sees the total
    logger.info("scan_job_message_ids_collected", total=emails_total)

    # Process in batches of 50.
    emails_processed = 0
    items_found = 0

    for batch_start in range(0, emails_total, 50):
        batch = message_ids[batch_start : batch_start + 50]

        try:
            inserted = await _process_batch(db, user, service, batch)
        except GmailReauthRequired:
            await _handle_reauth(db, user, job)
            return
        except Exception as exc:
            logger.error("scan_job_batch_failed", batch_start=batch_start, error=str(exc))
            await _fail_job(db, job, f"Batch error at offset {batch_start}: {exc}")
            return

        emails_processed += len(batch)
        items_found += inserted

        await db.execute(
            update(ScanJob)
            .where(ScanJob.id == job.id)
            .values(emails_processed=emails_processed, items_found=items_found)
        )
        await db.commit()  # commit after each batch so UI sees live progress
        logger.info(
            "scan_job_batch_done",
            emails_processed=emails_processed,
            emails_total=emails_total,
            items_found=items_found,
        )

    # Mark complete and update last_scan_at.
    now = datetime.now(UTC)
    await db.execute(
        update(ScanJob)
        .where(ScanJob.id == job.id)
        .values(status=ScanStatus.COMPLETE, completed_at=now)
    )
    await db.execute(
        update(User).where(User.id == user.id).values(last_scan_at=now)
    )
    await db.commit()
    logger.info("scan_job_complete", emails_processed=emails_processed, items_found=items_found)


async def process_next_job() -> None:
    """
    Claim and execute the next queued scan job using SELECT FOR UPDATE SKIP LOCKED.
    Called every 5 seconds by APScheduler.
    Bounded by _JOB_SEMAPHORE to a maximum of 3 concurrent jobs.
    """
    # Non-blocking acquire: if all 3 slots are full, skip this tick.
    if not _JOB_SEMAPHORE._value:  # noqa: SLF001
        return

    async with _JOB_SEMAPHORE:
        # Phase 1: claim a job in its own short-lived session.
        job_id = None
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ScanJob)
                .where(ScanJob.status == ScanStatus.QUEUED)
                .order_by(ScanJob.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job: ScanJob | None = result.scalar_one_or_none()
            if job is None:
                return

            await db.execute(
                update(ScanJob)
                .where(ScanJob.id == job.id)
                .values(
                    status=ScanStatus.RUNNING,
                    started_at=datetime.now(UTC),
                    locked_by=_WORKER_ID,
                    locked_at=datetime.now(UTC),
                )
            )
            await db.commit()
            job_id = job.id

        # Phase 2: reload the claimed job and run it in a fresh session.
        async with AsyncSessionLocal() as db:
            job_result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                return

            try:
                await _run_job(db, job)
            except Exception as exc:
                logger.exception("scan_job_unhandled_exception", error=str(exc))
                try:
                    async with AsyncSessionLocal() as fallback_db:
                        await _fail_job(fallback_db, job, f"Unhandled: {exc}")
                except Exception:
                    logger.exception("scan_job_fallback_fail_failed")
            finally:
                clear_log_context()
