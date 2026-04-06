from __future__ import annotations

from typing import Annotated, get_args

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import ItemCategory, get_db
from app.deps import CurrentUser
from app.schemas.common import SchemaBase
from app.schemas.item import (
    ExportBatchRequest,
    ExportBatchResult,
    ExtractedItemResponse,
    UrgencyTier,
)
from app.services.items import (
    build_ics,
    dismiss_item,
    export_item_to_gcal,
    export_items_batch,
    get_items,
    undismiss_item,
)

router = APIRouter(prefix="/api/items", tags=["items"])


class ItemsListResponse(BaseModel):
    items: list[ExtractedItemResponse]
    total: int


class CalendarExportResponse(SchemaBase):
    gcal_event_id: str
    html_link: str


def _parse_categories(raw_categories: str | None) -> list[ItemCategory] | None:
    if raw_categories is None or not raw_categories.strip():
        return None

    values = [value.strip() for value in raw_categories.split(",") if value.strip()]
    try:
        return [ItemCategory(value) for value in values]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid categories filter.",
        ) from exc


def _parse_urgency(raw_urgency: str | None) -> set[UrgencyTier] | None:
    if raw_urgency is None or not raw_urgency.strip():
        return None

    allowed = set(get_args(UrgencyTier))
    values = {value.strip() for value in raw_urgency.split(",") if value.strip()}
    if not values.issubset(allowed):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid urgency filter.",
        )
    return values


@router.get("", response_model=ItemsListResponse)
async def list_items(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    dismissed: bool = False,
    categories: str | None = None,
    urgency: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ItemsListResponse:
    result = await get_items(
        db,
        current_user,
        dismissed=dismissed,
        categories=_parse_categories(categories),
        urgency=_parse_urgency(urgency),
        limit=limit,
        offset=offset,
    )
    return ItemsListResponse.model_validate(result)


@router.post("/{item_id}/dismiss", response_model=ExtractedItemResponse)
async def dismiss_item_route(
    item_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractedItemResponse:
    return await dismiss_item(db, current_user, item_id)


@router.post("/{item_id}/undismiss", response_model=ExtractedItemResponse)
async def undismiss_item_route(
    item_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractedItemResponse:
    return await undismiss_item(db, current_user, item_id)


@router.post("/{item_id}/export", response_model=CalendarExportResponse)
async def export_item_route(
    item_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalendarExportResponse:
    result = await export_item_to_gcal(db, current_user, item_id)
    return CalendarExportResponse.model_validate(result)


@router.post("/export-batch", response_model=ExportBatchResult)
async def export_batch_route(
    payload: ExportBatchRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExportBatchResult:
    return await export_items_batch(
        db,
        current_user,
        [str(item_id) for item_id in payload.item_ids],
    )


@router.get("/export.ics")
async def export_ics_route(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    categories: str | None = None,
    urgency: str | None = None,
) -> Response:
    ics_content = await build_ics(
        db,
        current_user,
        categories=_parse_categories(categories),
        urgency=_parse_urgency(urgency),
    )
    return Response(content=ics_content, media_type="text/calendar; charset=utf-8")
