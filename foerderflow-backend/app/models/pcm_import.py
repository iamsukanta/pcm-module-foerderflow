"""Module PCM — External payroll import batch (Area J).

A ``payroll_import_batches`` row records one external payroll import (DATEV,
Personio, quarterly CSV, Diamant BAB). It is created on confirm/commit and, once
processed, feeds ``monthly_payrolls`` (quelle = IMPORT).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import ImportSourceType, PayrollImportStatus

if TYPE_CHECKING:
    pass


class PayrollImportBatch(Base):
    __tablename__ = "payroll_import_batches"
    __table_args__ = (
        Index("ix_payroll_import_batches_org_id", "org_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    source_type: Mapped[ImportSourceType] = mapped_column(
        pg_enum(ImportSourceType), nullable=False
    )
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[PayrollImportStatus] = mapped_column(
        pg_enum(PayrollImportStatus),
        default=PayrollImportStatus.PROCESSED,
        server_default="PROCESSED",
        nullable=False,
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_gross: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal(0), server_default="0", nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
