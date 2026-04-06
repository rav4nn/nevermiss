from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import (
    CONFIDENCE_LEVEL_ENUM,
    DATE_TYPE_ENUM,
    ITEM_CATEGORY_ENUM,
    Base,
    ConfidenceLevel,
    DateType,
    ItemCategory,
)

if TYPE_CHECKING:
    from app.models.user import User


class ExtractedItem(Base):
    __tablename__ = "extracted_items"
    __table_args__ = (
        UniqueConstraint("user_id", "source_message_id", "name", name="uq_user_msg_name"),
        Index(
            "idx_items_user_expiry",
            "user_id",
            "expiry_date",
            postgresql_where=text("dismissed = FALSE"),
        ),
        Index("idx_items_user_dismissed", "user_id", "dismissed"),
        Index("idx_items_user_category", "user_id", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[ItemCategory] = mapped_column(ITEM_CATEGORY_ENUM, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    date_type: Mapped[DateType] = mapped_column(DATE_TYPE_ENUM, nullable=False)
    confidence: Mapped[ConfidenceLevel] = mapped_column(CONFIDENCE_LEVEL_ENUM, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    source_sender: Mapped[str] = mapped_column(Text, nullable=False)
    source_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    dismissed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        default=False,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exported_to_gcal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        default=False,
    )
    gcal_event_id: Mapped[str | None] = mapped_column(Text)
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

    user: Mapped[User] = relationship(back_populates="items")
