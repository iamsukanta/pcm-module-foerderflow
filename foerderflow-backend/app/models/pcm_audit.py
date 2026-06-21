"""Module PCM — Salary-assignment audit log (Area O).

An immutable record of every contractual change to an employee: contract
updates, automatic Stufenaufstieg, and leave start/end. Required for funder
audit responses (O.1 / O.2). Rows are append-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import cuid_pk, pg_enum
from app.models.enums import AuditActionType

if TYPE_CHECKING:
    from app.models.payroll import Employee


class LogEmployeeSalaryAssignment(Base):
    __tablename__ = "log_employee_salary_assignments"
    __table_args__ = (
        Index("ix_log_employee_salary_assignments_org_id", "org_id"),
        Index("ix_log_employee_salary_assignments_employee_id", "employee_id"),
        Index(
            "ix_log_employee_salary_assignments_changed_at", "changed_at"
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    # The affected contract (null for leave events). SET NULL keeps the log if the
    # contract is later removed.
    salary_assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("employee_contracts.id", ondelete="SET NULL"), nullable=True
    )
    leave_period_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action_type: Mapped[AuditActionType] = mapped_column(
        pg_enum(AuditActionType), nullable=False
    )
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    employee: Mapped[Employee] = relationship(
        "Employee", foreign_keys=[employee_id]
    )
