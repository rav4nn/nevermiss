from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from app.core.db import ConfidenceLevel, DateType, ItemCategory
from app.schemas.common import SchemaBase

UrgencyTier = Literal[
    "critical",
    "urgent",
    "soon",
    "on_radar",
    "passive",
    "recently_expired",
]


class ExtractedItemResponse(SchemaBase):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    category: ItemCategory
    expiry_date: date
    date_type: DateType
    confidence: ConfidenceLevel
    notes: str | None
    source_sender: str
    source_date: datetime
    source_message_id: str
    dismissed: bool
    dismissed_at: datetime | None
    exported_to_gcal: bool
    gcal_event_id: str | None
    urgency: UrgencyTier
    days_remaining: int
    created_at: datetime
    updated_at: datetime


class ExportBatchRequest(SchemaBase):
    item_ids: list[uuid.UUID]


class ExportBatchItemResult(SchemaBase):
    item_id: uuid.UUID
    gcal_event_id: str | None
    error: str | None


class ExportBatchResult(SchemaBase):
    exported: int
    failed: int
    results: list[ExportBatchItemResult]
