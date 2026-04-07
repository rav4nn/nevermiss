from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import USER_TIER_ENUM, Base, UserTier

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.dismissed_signature import DismissedSignature
    from app.models.item import ExtractedItem
    from app.models.scan_job import ScanJob


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("digest_day_of_week BETWEEN 0 AND 6", name="ck_users_digest_day_of_week"),
        Index(
            "idx_users_tier",
            "tier",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    gmail_address: Mapped[str] = mapped_column(Text, nullable=False)
    google_sub: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    refresh_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_enc: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[UserTier] = mapped_column(
        USER_TIER_ENUM,
        nullable=False,
        server_default=text("'free'"),
        default=UserTier.FREE,
    )
    dodo_customer_id: Mapped[str | None] = mapped_column(Text, unique=True)
    dodo_subscription_id: Mapped[str | None] = mapped_column(Text, unique=True)
    timezone: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'UTC'"),
        default="UTC",
    )
    digest_day_of_week: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("1"),
        default=1,
    )
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_history_id: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    items: Mapped[list[ExtractedItem]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    scan_jobs: Mapped[list[ScanJob]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    dismissed_signatures: Mapped[list[DismissedSignature]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
