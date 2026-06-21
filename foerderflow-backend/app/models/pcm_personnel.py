"""Module PCM Layer-2 model: WochenstundenZuweisung (wochenstunden_zuweisungen).

Splits an employee's contracted weekly hours across cost centres / grant
projects. The sum across an employee's active assignments must not exceed the
contracted weekly hours (Doppelförderungs guard) — or, for PLAN_PERCENTAGE
assignments, must not exceed 100. Both checks live in the service layer.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, updated_at

if TYPE_CHECKING:
    from app.models.finanzplan import FinanzplanPosition
    from app.models.funding import FundingMeasure
    from app.models.master import CostCenter
    from app.models.payroll import Employee, EmployeeContract


class WochenstundenZuweisung(Base):
    __tablename__ = "wochenstunden_zuweisungen"
    __table_args__ = (
        Index("ix_wochenstunden_zuweisungen_org_id", "org_id"),
        Index("ix_wochenstunden_zuweisungen_employee_id", "employee_id"),
        Index(
            "ix_wochenstunden_zuweisungen_employee_id_effective_date",
            "employee_id",
            "effective_date",
        ),
        Index(
            "ix_wochenstunden_zuweisungen_salary_assignment_id",
            "salary_assignment_id",
        ),
        Index("ix_wochenstunden_zuweisungen_cost_center_id", "cost_center_id"),
        Index(
            "ix_wochenstunden_zuweisungen_funding_measure_id", "funding_measure_id"
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    # The spec's "salary assignment" is this codebase's EmployeeContract.
    salary_assignment_id: Mapped[str] = mapped_column(
        ForeignKey("employee_contracts.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=False
    )
    funding_measure_id: Mapped[str | None] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="SET NULL"), nullable=True
    )
    finanzplan_position_id: Mapped[str | None] = mapped_column(
        ForeignKey("finanzplan_positionen.id", ondelete="SET NULL"), nullable=True
    )
    # Hours/week — or plan percentage (e.g. 50.00 = 50%) for PLAN_PERCENTAGE.
    weekly_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    employee: Mapped[Employee] = relationship("Employee", foreign_keys=[employee_id])
    salary_assignment: Mapped[EmployeeContract] = relationship(
        "EmployeeContract", foreign_keys=[salary_assignment_id]
    )
    cost_center: Mapped[CostCenter] = relationship(
        "CostCenter", foreign_keys=[cost_center_id]
    )
    funding_measure: Mapped[FundingMeasure | None] = relationship(
        "FundingMeasure", foreign_keys=[funding_measure_id]
    )
    finanzplan_position: Mapped[FinanzplanPosition | None] = relationship(
        "FinanzplanPosition", foreign_keys=[finanzplan_position_id]
    )
