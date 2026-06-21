"""Salary-assignment audit log (Module PCM, Area O).

``log_assignment_change`` appends a row inside the caller's transaction (no
commit) so audit entries are atomic with the change they record. ``AuditService``
serves the O.1 list and O.2 detail screens.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import AuditActionType
from app.models.pcm_audit import LogEmployeeSalaryAssignment


def log_assignment_change(
    db: Session,
    *,
    org_id: str,
    employee_id: str,
    action_type: AuditActionType,
    summary: str,
    salary_assignment_id: str | None = None,
    leave_period_id: str | None = None,
    changed_by: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> LogEmployeeSalaryAssignment:
    """Append an audit row (no commit — the caller commits)."""
    row = LogEmployeeSalaryAssignment(
        org_id=org_id,
        employee_id=employee_id,
        salary_assignment_id=salary_assignment_id,
        leave_period_id=leave_period_id,
        action_type=action_type,
        changed_by=changed_by,
        changed_at=datetime.now(UTC),
        summary=summary,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(row)
    return row


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def _serialize(self, row: LogEmployeeSalaryAssignment) -> dict[str, Any]:
        emp = row.employee
        return {
            "id": row.id,
            "employee_id": row.employee_id,
            "employee_name": f"{emp.vorname} {emp.nachname}".strip() if emp else None,
            "salary_assignment_id": row.salary_assignment_id,
            "leave_period_id": row.leave_period_id,
            "action_type": row.action_type.value,
            "changed_by": row.changed_by,
            "changed_at": row.changed_at.isoformat() if row.changed_at else None,
            "summary": row.summary,
            "old_values": row.old_values,
            "new_values": row.new_values,
        }

    def list(self, org_id: str, filters: dict[str, str]) -> list[dict[str, Any]]:
        stmt = select(LogEmployeeSalaryAssignment).where(
            LogEmployeeSalaryAssignment.org_id == org_id
        )
        if filters.get("employee_id"):
            stmt = stmt.where(
                LogEmployeeSalaryAssignment.employee_id == filters["employee_id"]
            )
        if filters.get("action_type"):
            stmt = stmt.where(
                LogEmployeeSalaryAssignment.action_type == filters["action_type"]
            )
        if filters.get("changed_by"):
            stmt = stmt.where(
                LogEmployeeSalaryAssignment.changed_by == filters["changed_by"]
            )
        if filters.get("date_from"):
            try:
                df = date.fromisoformat(filters["date_from"])
                stmt = stmt.where(LogEmployeeSalaryAssignment.changed_at >= df)
            except ValueError:
                pass
        stmt = stmt.order_by(LogEmployeeSalaryAssignment.changed_at.desc())
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize(r) for r in rows]

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        row = self.db.execute(
            select(LogEmployeeSalaryAssignment).where(
                LogEmployeeSalaryAssignment.id == id_,
                LogEmployeeSalaryAssignment.org_id == org_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Protokolleintrag nicht gefunden.")
        return self._serialize(row)
