from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from app.core.db import ScanKind, ScanStatus
from app.schemas.common import SchemaBase


class ScanStartRequest(SchemaBase):
    kind: Literal[ScanKind.INITIAL, ScanKind.MANUAL]


class ScanStartResponse(SchemaBase):
    job_id: uuid.UUID
    status: Literal[ScanStatus.QUEUED]


class ScanJobResponse(SchemaBase):
    id: uuid.UUID
    user_id: uuid.UUID
    kind: ScanKind
    status: ScanStatus
    emails_total: int
    emails_processed: int
    items_found: int
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
