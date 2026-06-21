"""Module PCM payroll detail model: PayrollDetailLine (payroll_detail_lines).

One row per payroll component (BASE / ZULAGE / JSZ / BAV / …) of a MonthlyPayroll,
feeding the funder-specific VWN itemized breakdown. Cascade-deleted with the
parent payroll record.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum
from app.models.enums import BruttoType, PayrollDetailComponent

if TYPE_CHECKING:
    from app.models.payroll import MonthlyPayroll


class PayrollDetailLine(Base):
    __tablename__ = "payroll_detail_lines"
    __table_args__ = (
        Index("ix_payroll_detail_lines_org_id", "org_id"),
        Index("ix_payroll_detail_lines_monthly_payroll_id", "monthly_payroll_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    monthly_payroll_id: Mapped[str] = mapped_column(
        ForeignKey("monthly_payrolls.id", ondelete="CASCADE"), nullable=False
    )
    component: Mapped[PayrollDetailComponent] = mapped_column(
        pg_enum(PayrollDetailComponent), nullable=False
    )
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    brutto_type: Mapped[BruttoType] = mapped_column(pg_enum(BruttoType), nullable=False)
    # FK to the bonus_payments / bonus_templates / salary_adjustments record that
    # generated this line (traceability). Plain string until those tables land.
    source_record_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at()

    payroll: Mapped[MonthlyPayroll] = relationship(
        "MonthlyPayroll", back_populates="detail_lines"
    )
