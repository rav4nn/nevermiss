from __future__ import annotations

import uuid
from datetime import datetime

from app.core.db import UserTier
from app.schemas.common import SchemaBase


class UserResponse(SchemaBase):
    id: uuid.UUID
    email: str
    gmail_address: str
    tier: UserTier
    timezone: str
    digest_day_of_week: int
    last_scan_at: datetime | None
    created_at: datetime


class SessionCreateRequest(SchemaBase):
    google_sub: str
    email: str
    gmail_address: str
    refresh_token: str
    access_token: str
    access_token_expires_at: datetime
    timezone: str
