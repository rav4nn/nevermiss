from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Text, desc, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import SCAN_KIND_ENUM, SCAN_STATUS_ENUM, Base, ScanKind, ScanStatus

if TYPE_CHECKING:
    from app.models.user import User


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    __table_args__ = (
        Index("idx_scan_jobs_status", "status", "created_at"),
        Index("idx_scan_jobs_user", "user_id", desc("created_at")),
        Index(
            "uq_one_running_job_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
        ),
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
    )
    kind: Mapped[ScanKind] = mapped_column(SCAN_KIND_ENUM, nullable=False)
    status: Mapped[ScanStatus] = mapped_column(
        SCAN_STATUS_ENUM,
        nullable=False,
        server_default=text("'queued'"),
        default=ScanStatus.QUEUED,
    )
    since_date: Mapped[date | None] = mapped_column(Date)
    emails_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    emails_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    items_found: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
    )
    error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    user: Mapped[User] = relationship(back_populates="scan_jobs")
