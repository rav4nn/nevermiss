from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import ItemCategory
from app.core.errors import AppError, ErrorCode
from app.integrations.gcal import insert_calendar_event
from app.models.item import ExtractedItem
from app.models.user import User
from app.schemas.item import (
    ExportBatchItemResult,
    ExportBatchResult,
    ExtractedItemResponse,
    UrgencyTier,
)
from app.services import signatures
from app.services.rate_limit import check_rate_limit
from app.services.urgency import compute_urgency


def _build_items_query(
    user: User,
    *,
    dismissed: bool,
    categories: list[ItemCategory] | None,
) -> Select[tuple[ExtractedItem]]:
    statement = select(ExtractedItem).where(
        ExtractedItem.user_id == user.id,
        ExtractedItem.dismissed.is_(dismissed),
    )
    if categories:
        statement = statement.where(ExtractedItem.category.in_(categories))
    return statement.order_by(ExtractedItem.expiry_date.asc())


def _to_item_response(
    item: ExtractedItem,
    user_timezone: str,
) -> ExtractedItemResponse | None:
    urgency_result = compute_urgency(item.expiry_date, user_timezone)
    if urgency_result is None:
        return None

    urgency, days_remaining = urgency_result
    return ExtractedItemResponse.model_validate(
        {
            "id": item.id,
            "user_id": item.user_id,
            "name": item.name,
            "category": item.category,
            "expiry_date": item.expiry_date,
            "date_type": item.date_type,
            "confidence": item.confidence,
            "notes": item.notes,
            "source_sender": item.source_sender,
            "source_date": item.source_date,
            "source_message_id": item.source_message_id,
            "dismissed": item.dismissed,
            "dismissed_at": item.dismissed_at,
            "exported_to_gcal": item.exported_to_gcal,
            "gcal_event_id": item.gcal_event_id,
            "urgency": urgency,
            "days_remaining": days_remaining,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
    )


async def get_items(
    session: AsyncSession,
    user: User,
    *,
    dismissed: bool = False,
    categories: list[ItemCategory] | None = None,
    urgency: set[UrgencyTier] | None = None,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    result = await session.execute(
        _build_items_query(
            user,
            dismissed=dismissed,
            categories=categories,
        )
    )
    items = result.scalars().all()

    responses: list[ExtractedItemResponse] = []
    for item in items:
        response = _to_item_response(item, user.timezone)
        if response is None:
            continue
        if urgency is not None and response.urgency not in urgency:
            continue
        responses.append(response)

    total = len(responses)
    paginated = responses[offset : offset + limit]
    return {"items": paginated, "total": total}


async def _get_item_by_id(session: AsyncSession, item_id: str) -> ExtractedItem | None:
    try:
        parsed_id = uuid.UUID(item_id)
    except ValueError:
        return None
    result = await session.execute(select(ExtractedItem).where(ExtractedItem.id == parsed_id))
    return result.scalar_one_or_none()


async def _get_owned_item(
    session: AsyncSession,
    user: User,
    item_id: str,
) -> ExtractedItem:
    item = await _get_item_by_id(session, item_id)
    if item is None:
        raise AppError(
            ErrorCode.NOT_FOUND,
            "Item not found.",
            status_code=404,
        )
    if item.user_id != user.id:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "You do not have access to this item.",
            status_code=403,
        )
    return item


async def dismiss_item(
    session: AsyncSession,
    user: User,
    item_id: str,
) -> ExtractedItemResponse:
    item = await _get_owned_item(session, user, item_id)
    item.dismissed = True
    item.dismissed_at = datetime.now(UTC)
    signature = signatures.compute_signature(
        item.name,
        item.category.value,
        item.expiry_date,
    )
    await signatures.add_dismissed(session, user.id, signature)
    await session.commit()
    await session.refresh(item)
    response = _to_item_response(item, user.timezone)
    if response is None:
        raise AppError(ErrorCode.NOT_FOUND, "Item not found.", status_code=404)
    return response


async def undismiss_item(
    session: AsyncSession,
    user: User,
    item_id: str,
) -> ExtractedItemResponse:
    item = await _get_owned_item(session, user, item_id)
    item.dismissed = False
    item.dismissed_at = None
    signature = signatures.compute_signature(
        item.name,
        item.category.value,
        item.expiry_date,
    )
    await signatures.remove_dismissed(session, user.id, signature)
    await session.commit()
    await session.refresh(item)
    response = _to_item_response(item, user.timezone)
    if response is None:
        raise AppError(ErrorCode.NOT_FOUND, "Item not found.", status_code=404)
    return response


async def export_item_to_gcal(
    session: AsyncSession,
    user: User,
    item_id: str,
) -> dict[str, str]:
    check_rate_limit(f"export:{user.id}", limit=30, window_seconds=3600)
    item = await _get_owned_item(session, user, item_id)
    result = insert_calendar_event(user, item)
    item.gcal_event_id = result["gcalEventId"]
    item.exported_to_gcal = True
    await session.commit()
    await session.refresh(item)
    return result


async def export_items_batch(
    session: AsyncSession,
    user: User,
    item_ids: list[str],
) -> ExportBatchResult:
    check_rate_limit(f"export:{user.id}", limit=30, window_seconds=3600)
    results: list[ExportBatchItemResult] = []
    exported = 0
    failed = 0

    for item_id in item_ids:
        try:
            result = await _export_item_without_rate_limit(session, user, item_id)
        except AppError as exc:
            failed += 1
            results.append(
                ExportBatchItemResult(
                    item_id=item_id,
                    gcal_event_id=None,
                    error=exc.message,
                )
            )
        else:
            exported += 1
            results.append(
                ExportBatchItemResult(
                    item_id=item_id,
                    gcal_event_id=result["gcalEventId"],
                    error=None,
                )
            )

    return ExportBatchResult(exported=exported, failed=failed, results=results)


async def _export_item_without_rate_limit(
    session: AsyncSession,
    user: User,
    item_id: str,
) -> dict[str, str]:
    item = await _get_owned_item(session, user, item_id)
    result = insert_calendar_event(user, item)
    item.gcal_event_id = result["gcalEventId"]
    item.exported_to_gcal = True
    await session.commit()
    await session.refresh(item)
    return result


async def build_ics(
    session: AsyncSession,
    user: User,
    *,
    categories: list[ItemCategory] | None = None,
    urgency: set[UrgencyTier] | None = None,
) -> str:
    check_rate_limit(f"export:{user.id}", limit=30, window_seconds=3600)
    result = await get_items(
        session,
        user,
        dismissed=False,
        categories=categories,
        urgency=urgency,
        limit=1000000,
        offset=0,
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NeverMiss//Calendar Export//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for item in result["items"]:
        source_date = item.source_date.isoformat().replace("+00:00", "Z")
        description = (
            f"Category: {item.category}\n"
            f"Source: {item.source_sender} on {source_date}\n"
            "Detected by NeverMiss"
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{item.id}@nevermiss.my",
                f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{_escape_ics_text(item.name)}",
                f"DESCRIPTION:{_escape_ics_text(description)}",
                f"DTSTART;VALUE=DATE:{item.expiry_date.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(item.expiry_date + timedelta(days=1)).strftime('%Y%m%d')}",
            ]
        )
        lines.extend(
            [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                "DESCRIPTION:Reminder",
                "TRIGGER:-P7D",
                "END:VALARM",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                "DESCRIPTION:Reminder",
                "TRIGGER:-P1D",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\n", r"\n")
    )
