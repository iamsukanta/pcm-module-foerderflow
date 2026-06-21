"""Module PCM — Bonuses & Adjustments models (Areas G & H).

  BonusTemplate (bonus_templates)   — org-level rules applied automatically to
                                      matching employees at each payroll/forecast.
  BonusPayment  (bonus_payments)    — per-employee bonus; overrides a template of
                                      the same type for the same period.
  SalaryAdjustment (salary_adjustments) — per-employee monthly addition/deduction
                                      (Münchenzulage, Jobticket, …).

``amount`` is Numeric(14,4): a € value for FIXED/ADDITION/DEDUCTION, or a percent
(e.g. 2.0000 = 2 %) for PERCENT / REFERENCE_MONTH bonuses.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import (
    AdjustmentType,
    BonusApplicableTo,
    BonusType,
    BruttoType,
    ProrationRule,
)

if TYPE_CHECKING:
    pass


class BonusTemplate(Base):
    __tablename__ = "bonus_templates"
    __table_args__ = (Index("ix_bonus_templates_org_id", "org_id"),)

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Eligibility — null tariff_code = all tariffs; null group bounds = all groups.
    tariff_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary_group_min: Mapped[str | None] = mapped_column(String(20), nullable=True)
    salary_group_max: Mapped[str | None] = mapped_column(String(20), nullable=True)
    applicable_to: Mapped[BonusApplicableTo] = mapped_column(
        pg_enum(BonusApplicableTo),
        default=BonusApplicableTo.ALL,
        server_default="ALL",
        nullable=False,
    )
    type: Mapped[BonusType] = mapped_column(pg_enum(BonusType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    brutto_type: Mapped[BruttoType] = mapped_column(pg_enum(BruttoType), nullable=False)
    proration_rule: Mapped[ProrationRule] = mapped_column(
        pg_enum(ProrationRule),
        default=ProrationRule.FULL,
        server_default="FULL",
        nullable=False,
    )
    reference_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prorate_by_employment_period: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class BonusPayment(Base):
    __tablename__ = "bonus_payments"
    __table_args__ = (
        Index("ix_bonus_payments_org_id", "org_id"),
        Index("ix_bonus_payments_employee_id", "employee_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[BonusType] = mapped_column(pg_enum(BonusType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    brutto_type: Mapped[BruttoType] = mapped_column(pg_enum(BruttoType), nullable=False)
    proration_rule: Mapped[ProrationRule] = mapped_column(
        pg_enum(ProrationRule),
        default=ProrationRule.FULL,
        server_default="FULL",
        nullable=False,
    )
    reference_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prorate_by_employment_period: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Provenance if generated from a template (manual rows = null).
    source_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("bonus_templates.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class SalaryAdjustment(Base):
    __tablename__ = "salary_adjustments"
    __table_args__ = (
        Index("ix_salary_adjustments_org_id", "org_id"),
        Index("ix_salary_adjustments_employee_id", "employee_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[AdjustmentType] = mapped_column(
        pg_enum(AdjustmentType), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    brutto_type: Mapped[BruttoType] = mapped_column(pg_enum(BruttoType), nullable=False)
    proration_rule: Mapped[ProrationRule] = mapped_column(
        pg_enum(ProrationRule),
        default=ProrationRule.FULL,
        server_default="FULL",
        nullable=False,
    )
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
