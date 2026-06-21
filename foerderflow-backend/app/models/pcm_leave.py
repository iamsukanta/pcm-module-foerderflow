"""Module PCM — Leave & Absence model: EmployeeLeavePeriod
(employee_leave_periods).

Records an employee absence (Elternzeit, Mutterschutz, Langzeiterkrankung, …)
and optionally links a PLACEHOLDER replacement employee. While a leave period is
active, the absent employee's payroll is suppressed (status = ON_LEAVE, gross 0)
for covered months. A period is ACTIVE while ``actual_end_date IS NULL`` and
ENDED once the return is recorded.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import LeaveType

if TYPE_CHECKING:
    from app.models.payroll import Employee


class EmployeeLeavePeriod(Base):
    __tablename__ = "employee_leave_periods"
    __table_args__ = (
        Index("ix_employee_leave_periods_org_id", "org_id"),
        Index("ix_employee_leave_periods_employee_id", "employee_id"),
        Index(
            "ix_employee_leave_periods_employee_id_start_date",
            "employee_id",
            "start_date",
        ),
        Index(
            "ix_employee_leave_periods_replacement_employee_id",
            "replacement_employee_id",
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    leave_type: Mapped[LeaveType] = mapped_column(pg_enum(LeaveType), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    replacement_employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    funder_notification_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    funder_notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    employee: Mapped[Employee] = relationship(
        "Employee", foreign_keys=[employee_id]
    )
    replacement: Mapped[Employee | None] = relationship(
        "Employee", foreign_keys=[replacement_employee_id]
    )
