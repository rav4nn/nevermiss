from __future__ import annotations

from collections.abc import AsyncGenerator
from enum import StrEnum

from sqlalchemy import Enum as SqlEnum
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


class UserTier(StrEnum):
    FREE = "free"
    PRO = "pro"


class ItemCategory(StrEnum):
    SUBSCRIPTION = "subscription"
    INSURANCE = "insurance"
    VOUCHER = "voucher"
    WARRANTY = "warranty"
    DOCUMENT = "document"
    FINANCE = "finance"
    DOMAIN = "domain"
    MEMBERSHIP = "membership"
    OTHER = "other"


class DateType(StrEnum):
    EXPIRY = "expiry"
    RENEWAL = "renewal"
    DEADLINE = "deadline"
    END_OF_OFFER = "end_of_offer"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class ScanKind(StrEnum):
    INITIAL = "initial"
    WEEKLY = "weekly"
    MANUAL = "manual"


def _values(enum):  # type: ignore[type-arg]
    return [e.value for e in enum]


USER_TIER_ENUM = SqlEnum(UserTier, name="user_tier", create_type=False, values_callable=_values)
ITEM_CATEGORY_ENUM = SqlEnum(ItemCategory, name="item_category", create_type=False, values_callable=_values)
DATE_TYPE_ENUM = SqlEnum(DateType, name="date_type", create_type=False, values_callable=_values)
CONFIDENCE_LEVEL_ENUM = SqlEnum(
    ConfidenceLevel,
    name="confidence_level",
    create_type=False,
    values_callable=_values,
)
SCAN_STATUS_ENUM = SqlEnum(ScanStatus, name="scan_status", create_type=False, values_callable=_values)
SCAN_KIND_ENUM = SqlEnum(ScanKind, name="scan_kind", create_type=False, values_callable=_values)

settings = get_settings()
engine = create_async_engine(settings.database_url, future=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
