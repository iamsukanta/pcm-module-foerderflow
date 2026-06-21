"""Leave & Absence controllers (Module PCM, Area F).

Org-scoped ``{data}``/``APIError`` envelopes. A leave period is ACTIVE while
``actual_end_date IS NULL`` and ENDED once a return is recorded. Recording a
return closes the linked PLACEHOLDER replacement's open hour assignments.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import AuditActionType, EmployeeType, LeaveType
from app.models.payroll import Employee
from app.models.pcm_leave import EmployeeLeavePeriod
from app.models.pcm_personnel import WochenstundenZuweisung
from app.services.pcm._validate import opt_date, parse_date, req_str
from app.services.pcm.audit_service import log_assignment_change


def is_on_leave(
    db: Session, *, org_id: str, employee_id: str, month: date
) -> EmployeeLeavePeriod | None:
    """Return the leave period suppressing ``employee_id`` for the calendar month
    of ``month`` (first-of-month), or None. A period covers the month if it
    overlaps any day of it."""
    month_start = month.replace(day=1)
    month_end = month_start + relativedelta(months=1) - timedelta(days=1)
    rows = (
        db.execute(
            select(EmployeeLeavePeriod).where(
                EmployeeLeavePeriod.org_id == org_id,
                EmployeeLeavePeriod.employee_id == employee_id,
                EmployeeLeavePeriod.start_date <= month_end,
            )
        )
        .scalars()
        .all()
    )
    for lp in rows:
        end = lp.actual_end_date
        if end is None or end >= month_start:
            return lp
    return None


def _status(lp: EmployeeLeavePeriod) -> str:
    return "ENDED" if lp.actual_end_date is not None else "ACTIVE"


class LeaveService:
    def __init__(self, db: Session):
        self.db = db

    def _serialize(self, lp: EmployeeLeavePeriod) -> dict[str, Any]:
        emp = lp.employee
        rep = lp.replacement
        return {
            "id": lp.id,
            "employee_id": lp.employee_id,
            "employee_name": f"{emp.vorname} {emp.nachname}".strip() if emp else None,
            "leave_type": lp.leave_type.value,
            "start_date": lp.start_date.isoformat(),
            "expected_end_date": lp.expected_end_date.isoformat() if lp.expected_end_date else None,
            "actual_end_date": lp.actual_end_date.isoformat() if lp.actual_end_date else None,
            "replacement_employee_id": lp.replacement_employee_id,
            "replacement_name": f"{rep.vorname} {rep.nachname}".strip() if rep else None,
            "funder_notification_required": lp.funder_notification_required,
            "funder_notification_sent_at": (
                lp.funder_notification_sent_at.isoformat()
                if lp.funder_notification_sent_at
                else None
            ),
            "note": lp.note,
            "status": _status(lp),
            "created_at": lp.created_at.isoformat() if lp.created_at else None,
        }

    # ── reads ─────────────────────────────────────────────────────────────────
    def list(self, org_id: str, filters: dict[str, str]) -> list[dict[str, Any]]:
        stmt = select(EmployeeLeavePeriod).where(
            EmployeeLeavePeriod.org_id == org_id
        )
        if filters.get("employee_id"):
            stmt = stmt.where(EmployeeLeavePeriod.employee_id == filters["employee_id"])
        if filters.get("leave_type"):
            stmt = stmt.where(EmployeeLeavePeriod.leave_type == filters["leave_type"])
        status = filters.get("status")
        if status == "active":
            stmt = stmt.where(EmployeeLeavePeriod.actual_end_date.is_(None))
        elif status == "ended":
            stmt = stmt.where(EmployeeLeavePeriod.actual_end_date.is_not(None))
        stmt = stmt.order_by(EmployeeLeavePeriod.start_date.desc())
        rows = self.db.execute(stmt).scalars().all()
        out = [self._serialize(lp) for lp in rows]
        if filters.get("notification_pending") == "true":
            out = [
                o
                for o in out
                if o["status"] == "ACTIVE"
                and o["funder_notification_required"]
                and o["funder_notification_sent_at"] is None
            ]
        return out

    def _get(self, org_id: str, id_: str) -> EmployeeLeavePeriod:
        lp = self.db.execute(
            select(EmployeeLeavePeriod).where(
                EmployeeLeavePeriod.id == id_,
                EmployeeLeavePeriod.org_id == org_id,
            )
        ).scalar_one_or_none()
        if lp is None:
            raise APIError(404, "NOT_FOUND", "Abwesenheit nicht gefunden.")
        return lp

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        return self._serialize(self._get(org_id, id_))

    def _employee(self, org_id: str, employee_id: str) -> Employee:
        emp = self.db.execute(
            select(Employee).where(
                Employee.id == employee_id, Employee.org_id == org_id
            )
        ).scalar_one_or_none()
        if emp is None:
            raise APIError(404, "EMPLOYEE_NOT_FOUND", "Mitarbeiter:in nicht gefunden.")
        return emp

    # ── writes ────────────────────────────────────────────────────────────────
    def create(
        self, org_id: str, body: dict[str, Any], *, changed_by: str | None = None
    ) -> dict[str, Any]:
        employee_id = req_str(body, "employee_id")
        emp = self._employee(org_id, employee_id)
        if emp.employee_type == EmployeeType.PLACEHOLDER:
            raise APIError(
                422,
                "INVALID_EMPLOYEE_TYPE",
                "Für Platzhalter-Mitarbeitende kann keine Abwesenheit erfasst werden.",
            )
        leave_type = req_str(body, "leave_type")
        if leave_type not in {t.value for t in LeaveType}:
            raise APIError(422, "INVALID_LEAVE_TYPE", "Ungültige Abwesenheitsart.")
        start_date = parse_date(body.get("start_date"), "start_date")
        expected_end = opt_date(body.get("expected_end_date"), "expected_end_date")
        if expected_end is not None and expected_end < start_date:
            raise APIError(422, "INVALID_DATE_RANGE", "Ende darf nicht vor Beginn liegen.")
        replacement_id = body.get("replacement_employee_id") or None
        if replacement_id:
            rep = self._employee(org_id, replacement_id)
            if rep.employee_type != EmployeeType.PLACEHOLDER:
                raise APIError(
                    422,
                    "INVALID_REPLACEMENT",
                    "Vertretung muss eine Platzhalter-Mitarbeiter:in sein.",
                )
        lp = EmployeeLeavePeriod(
            org_id=org_id,
            employee_id=employee_id,
            leave_type=LeaveType(leave_type),
            start_date=start_date,
            expected_end_date=expected_end,
            replacement_employee_id=replacement_id,
            funder_notification_required=bool(body.get("funder_notification_required", False)),
            note=(body.get("note") or None),
        )
        self.db.add(lp)
        self.db.flush()
        log_assignment_change(
            self.db,
            org_id=org_id,
            employee_id=employee_id,
            action_type=AuditActionType.LEAVE_START,
            leave_period_id=lp.id,
            summary=(
                f"{emp.vorname} {emp.nachname}: {leave_type} ab "
                f"{start_date.isoformat()}"
            ),
            new_values={
                "leave_type": leave_type,
                "start_date": start_date.isoformat(),
                "expected_end_date": expected_end.isoformat() if expected_end else None,
            },
            changed_by=changed_by,
        )
        self.db.commit()
        self.db.refresh(lp)
        return self._serialize(lp)

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        lp = self._get(org_id, id_)
        if "expected_end_date" in body:
            lp.expected_end_date = opt_date(body["expected_end_date"], "expected_end_date")
        if "note" in body:
            lp.note = body["note"] or None
        if "funder_notification_required" in body:
            lp.funder_notification_required = bool(body["funder_notification_required"])
        if "replacement_employee_id" in body:
            rid = body["replacement_employee_id"] or None
            if rid:
                rep = self._employee(org_id, rid)
                if rep.employee_type != EmployeeType.PLACEHOLDER:
                    raise APIError(422, "INVALID_REPLACEMENT", "Vertretung muss Platzhalter sein.")
            lp.replacement_employee_id = rid
        self.db.commit()
        self.db.refresh(lp)
        return self._serialize(lp)

    def mark_notification_sent(self, org_id: str, id_: str) -> dict[str, Any]:
        lp = self._get(org_id, id_)
        lp.funder_notification_sent_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(lp)
        return self._serialize(lp)

    def record_return(
        self, org_id: str, id_: str, body: dict[str, Any], *, changed_by: str | None = None
    ) -> dict[str, Any]:
        lp = self._get(org_id, id_)
        actual_end = parse_date(body.get("actual_end_date"), "actual_end_date")
        if actual_end < lp.start_date:
            raise APIError(422, "INVALID_DATE_RANGE", "Rückkehr darf nicht vor Beginn liegen.")
        lp.actual_end_date = actual_end
        log_assignment_change(
            self.db,
            org_id=org_id,
            employee_id=lp.employee_id,
            action_type=AuditActionType.LEAVE_END,
            leave_period_id=lp.id,
            summary=f"Rückkehr aus Abwesenheit am {actual_end.isoformat()}",
            new_values={"actual_end_date": actual_end.isoformat()},
            changed_by=changed_by,
        )
        # Close the replacement's open hour assignments at return - 1 day.
        if lp.replacement_employee_id:
            reps = (
                self.db.execute(
                    select(WochenstundenZuweisung).where(
                        WochenstundenZuweisung.org_id == org_id,
                        WochenstundenZuweisung.employee_id == lp.replacement_employee_id,
                        WochenstundenZuweisung.end_date.is_(None),
                    )
                )
                .scalars()
                .all()
            )
            for r in reps:
                r.end_date = actual_end - timedelta(days=1)
        self.db.commit()
        self.db.refresh(lp)
        return self._serialize(lp)

    # ── Fristen integration (Area P) ──────────────────────────────────────────
    def fristen_tasks(self, org_id: str) -> dict[str, Any]:
        """PCM-generated deadline tasks for the Fristen dashboard:
        LEAVE_NOTIFICATION (funder notice pending) + RETURN_CHECK (return due ≤14d)."""
        today = date.today()
        active = (
            self.db.execute(
                select(EmployeeLeavePeriod).where(
                    EmployeeLeavePeriod.org_id == org_id,
                    EmployeeLeavePeriod.actual_end_date.is_(None),
                )
            )
            .scalars()
            .all()
        )
        tasks: list[dict[str, Any]] = []
        for lp in active:
            emp = lp.employee
            name = f"{emp.vorname} {emp.nachname}".strip() if emp else "?"
            if lp.funder_notification_required and lp.funder_notification_sent_at is None:
                tasks.append({
                    "type": "LEAVE_NOTIFICATION",
                    "leave_period_id": lp.id,
                    "employee_name": name,
                    "title": f"Fördergeberin benachrichtigen: {name} — "
                             f"{lp.leave_type.value} ab {lp.start_date.isoformat()}",
                    "due_date": (lp.start_date - timedelta(days=5)).isoformat(),
                })
            if lp.expected_end_date is not None:
                days = (lp.expected_end_date - today).days
                if 0 <= days <= 14:
                    tasks.append({
                        "type": "RETURN_CHECK",
                        "leave_period_id": lp.id,
                        "employee_name": name,
                        "title": f"Rückkehr von {name} erwartet am "
                                 f"{lp.expected_end_date.isoformat()} — Kostenplanung prüfen",
                        "due_date": (lp.expected_end_date - timedelta(days=7)).isoformat(),
                    })
        tasks.sort(key=lambda t: t["due_date"])
        return {"total": len(tasks), "tasks": tasks}

    # ── placeholder employees (F.5) ───────────────────────────────────────────
    def list_placeholders(self, org_id: str) -> list[dict[str, Any]]:
        placeholders = (
            self.db.execute(
                select(Employee).where(
                    Employee.org_id == org_id,
                    Employee.employee_type == EmployeeType.PLACEHOLDER,
                )
            )
            .scalars()
            .all()
        )
        linked = {
            lp.replacement_employee_id: lp
            for lp in self.db.execute(
                select(EmployeeLeavePeriod).where(
                    EmployeeLeavePeriod.org_id == org_id,
                    EmployeeLeavePeriod.replacement_employee_id.is_not(None),
                )
            ).scalars()
        }
        out = []
        for emp in placeholders:
            lp = linked.get(emp.id)
            out.append(
                {
                    "id": emp.id,
                    "employee_code": emp.employee_code,
                    "name": f"{emp.vorname} {emp.nachname}".strip(),
                    "leave_period_id": lp.id if lp else None,
                    "status": "ACTIVE" if (lp and _status(lp) == "ACTIVE") else "CLOSED",
                }
            )
        return out

    def create_placeholder(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        nachname = req_str(body, "nachname")
        vorname = (body.get("vorname") or "Vertretung").strip()
        count = self.db.execute(
            select(func.count())
            .select_from(Employee)
            .where(
                Employee.org_id == org_id,
                Employee.employee_type == EmployeeType.PLACEHOLDER,
            )
        ).scalar_one()
        emp = Employee(
            org_id=org_id,
            employee_code=f"VTR-{int(count) + 1:03d}",
            vorname=vorname,
            nachname=nachname,
            eintrittsdatum=opt_date(body.get("eintrittsdatum"), "eintrittsdatum")
            or date.today(),
            employee_type=EmployeeType.PLACEHOLDER,
        )
        self.db.add(emp)
        self.db.commit()
        self.db.refresh(emp)
        return {
            "id": emp.id,
            "employee_code": emp.employee_code,
            "name": f"{emp.vorname} {emp.nachname}".strip(),
            "leave_period_id": None,
            "status": "CLOSED",
        }
