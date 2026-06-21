"""Module PCM tariff model: SalaryTariff (salary_tariffs) + SalaryLevel
(salary_levels).

These replace the validity-window-agnostic `tarif_tabelle` for PCM purposes.
A SalaryTariff row is active for months where `valid_from <= month <= valid_to`
(null valid_to = open-ended). Two non-overlapping rows for the same
(tariff_code, salary_group, level, is_proposed) express a mid-year tariff change
(e.g. TVöD 25er Jan–Apr / 26er May–Dec).

The no-overlap rule per (org_id, tariff_code, salary_group, level, is_proposed)
is enforced at the service layer — a range no-overlap constraint is not portable
to the SQLite test harness, so it is validated in Python before insert.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, updated_at

if TYPE_CHECKING:
    pass


class SalaryTariff(Base):
    __tablename__ = "salary_tariffs"
    __table_args__ = (
        Index("ix_salary_tariffs_org_id", "org_id"),
        # Supports the per-month tariff lookup (org + code + group + level).
        Index(
            "ix_salary_tariffs_lookup",
            "org_id",
            "tariff_code",
            "salary_group",
            "level",
            "is_proposed",
        ),
        Index("ix_salary_tariffs_deleted_at", "deleted_at"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    tariff_code: Mapped[str] = mapped_column(String(50), nullable=False)
    salary_group: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    standard_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_proposed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Betriebliche Altersversorgung rate for this tariff; org default if null.
    bav_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    # Soft-delete: retire a row without dropping audit/payroll history. All Tariff
    # Registry reads, the overlap guard and the resolver skip non-null rows.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    levels: Mapped[list[SalaryLevel]] = relationship(
        back_populates="tariff", cascade="all, delete-orphan"
    )


class SalaryLevel(Base):
    __tablename__ = "salary_levels"
    __table_args__ = (
        UniqueConstraint("tariff_id", "salary_group", "level_no"),
        Index("ix_salary_levels_org_id", "org_id"),
        Index("ix_salary_levels_tariff_id", "tariff_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    tariff_id: Mapped[str] = mapped_column(
        ForeignKey("salary_tariffs.id", ondelete="CASCADE"), nullable=False
    )
    salary_group: Mapped[str] = mapped_column(String(20), nullable=False)
    level_no: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # null = maximum level (Promotion Job stops advancing).
    months_to_next_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = created_at()

    tariff: Mapped[SalaryTariff] = relationship(back_populates="levels")
