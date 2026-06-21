"""Module PCM — Payroll period lock (Area I).

A ``payroll_periods`` row tracks the lock state of one calendar month within a
fiscal year. It is created lazily (on first run or lock). A LOCKED period cannot
be re-run; its ``monthly_payrolls`` become the legal payroll record for the
month. NOT_STARTED is derived (no row + no payrolls), so only OPEN / LOCKED are
persisted.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import PayrollPeriodStatus

if TYPE_CHECKING:
    pass


class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        UniqueConstraint("org_id", "monat"),
        Index("ix_payroll_periods_org_id_fiscal_year_id", "org_id", "fiscal_year_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False
    )
    monat: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PayrollPeriodStatus] = mapped_column(
        pg_enum(PayrollPeriodStatus),
        default=PayrollPeriodStatus.OPEN,
        server_default="OPEN",
        nullable=False,
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
