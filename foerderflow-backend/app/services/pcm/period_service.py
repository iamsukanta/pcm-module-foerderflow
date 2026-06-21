"""Payroll period lifecycle controllers (Module PCM, Area I).

Periods are months of a fiscal year. Status is derived: NOT_STARTED (no payrolls),
CALCULATED (payrolls exist, OPEN), LOCKED (frozen). Only OPEN/LOCKED are persisted
in ``payroll_periods``; the period row is created lazily on lock.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import FiscalYearStatus, PayrollPeriodStatus, PayrollStatus
from app.models.master import FiscalYear
from app.models.payroll import Employee, MonthlyPayroll
from app.models.pcm_leave import EmployeeLeavePeriod
from app.models.pcm_period import PayrollPeriod
from app.services.pcm.leave_service import is_on_leave
from app.services.personal.berechnung import get_aktiver_vertrag
from app.utils.serialization import decimal_str

_MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def assert_period_not_locked(db: Session, *, org_id: str, monat: date) -> None:
    """Block writes to a LOCKED payroll period (Area I.7)."""
    period = db.execute(
        select(PayrollPeriod).where(
            PayrollPeriod.org_id == org_id,
            PayrollPeriod.monat == monat.replace(day=1),
        )
    ).scalar_one_or_none()
    if period is not None and period.status == PayrollPeriodStatus.LOCKED:
        raise APIError(
            423,
            "PERIOD_LOCKED",
            "Die Abrechnungsperiode ist gesperrt und kann nicht erneut berechnet werden.",
        )


class PayrollPeriodService:
    def __init__(self, db: Session):
        self.db = db

    def _fiscal_year(self, org_id: str, fiscal_year_id: str) -> FiscalYear:
        fy = self.db.get(FiscalYear, fiscal_year_id)
        if fy is None or fy.org_id != org_id:
            raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        return fy

    @staticmethod
    def _months(fy: FiscalYear) -> Iterable[date]:
        cur = fy.beginn.replace(day=1)
        while cur <= fy.ende:
            yield cur
            cur = cur + relativedelta(months=1)

    def _period(self, org_id: str, monat: date) -> PayrollPeriod | None:
        return self.db.execute(
            select(PayrollPeriod).where(
                PayrollPeriod.org_id == org_id,
                PayrollPeriod.monat == monat.replace(day=1),
            )
        ).scalar_one_or_none()

    # ── I.1 overview ───────────────────────────────────────────────────────────
    def overview(self, org_id: str, fiscal_year_id: str) -> dict[str, Any]:
        fy = self._fiscal_year(org_id, fiscal_year_id)
        rows: list[dict[str, Any]] = []
        for monat in self._months(fy):
            payrolls = (
                self.db.execute(
                    select(MonthlyPayroll).where(
                        MonthlyPayroll.org_id == org_id,
                        MonthlyPayroll.fiscal_year_id == fiscal_year_id,
                        MonthlyPayroll.monat == monat,
                    )
                )
                .scalars()
                .all()
            )
            period = self._period(org_id, monat)
            locked = period is not None and period.status == PayrollPeriodStatus.LOCKED
            total_ag = sum((p.betrag_ag_brutto for p in payrolls), Decimal(0))
            errors = sum(1 for p in payrolls if p.status == PayrollStatus.ERROR)
            on_leave = sum(1 for p in payrolls if p.status == PayrollStatus.ON_LEAVE)
            last_run = max(
                (p.updated_at for p in payrolls if p.updated_at), default=None
            )
            status = "LOCKED" if locked else "CALCULATED" if payrolls else "NOT_STARTED"
            rows.append({
                "monat": monat.isoformat(),
                "label": f"{_MONTHS_DE[monat.month - 1]} {monat.year}",
                "status": status,
                "employee_count": len(payrolls),
                "total_ag_brutto": decimal_str(total_ag),
                "error_count": errors,
                "on_leave_count": on_leave,
                "last_run_at": last_run.isoformat() if last_run else None,
                "locked_at": period.locked_at.isoformat()
                if period and period.locked_at
                else None,
            })
        return {"fiscal_year_id": fiscal_year_id, "jahr": fy.jahr, "periods": rows}

    # ── I.4 results ────────────────────────────────────────────────────────────
    def results(
        self, org_id: str, fiscal_year_id: str, monat: date
    ) -> dict[str, Any]:
        monat = monat.replace(day=1)
        payrolls = (
            self.db.execute(
                select(MonthlyPayroll, Employee)
                .join(Employee, MonthlyPayroll.employee_id == Employee.id)
                .where(
                    MonthlyPayroll.org_id == org_id,
                    MonthlyPayroll.fiscal_year_id == fiscal_year_id,
                    MonthlyPayroll.monat == monat,
                )
                .order_by(Employee.nachname, Employee.vorname)
            )
            .all()
        )
        rows = []
        total_ag = total_an = total_bav = Decimal(0)
        by_status: dict[str, int] = {}
        for p, emp in payrolls:
            total_ag += p.betrag_ag_brutto
            total_an += p.betrag_an_brutto
            total_bav += p.bav_amount
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
            rows.append({
                "payroll_id": p.id,
                "employee_id": emp.id,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                "status": p.status.value,
                "actual_salary": decimal_str(p.actual_salary),
                "an_brutto": decimal_str(p.betrag_an_brutto),
                "ag_brutto": decimal_str(p.betrag_ag_brutto),
                "bav_amount": decimal_str(p.bav_amount),
                "fringe_benefits_amount": decimal_str(p.fringe_benefits_amount),
                "allocation_count": len(p.allocations),
                "quelle": p.quelle,
            })
        period = self._period(org_id, monat)
        locked = period is not None and period.status == PayrollPeriodStatus.LOCKED
        return {
            "monat": monat.isoformat(),
            "label": f"{_MONTHS_DE[monat.month - 1]} {monat.year}",
            "locked": locked,
            "summary": {
                "employee_count": len(rows),
                "total_ag_brutto": decimal_str(total_ag),
                "total_an_brutto": decimal_str(total_an),
                "total_bav": decimal_str(total_bav),
                "by_status": by_status,
            },
            "rows": rows,
        }

    # ── I.2 preflight ──────────────────────────────────────────────────────────
    def preflight(
        self, org_id: str, fiscal_year_id: str, monat: date
    ) -> dict[str, Any]:
        monat = monat.replace(day=1)
        self._fiscal_year(org_id, fiscal_year_id)
        employees = (
            self.db.execute(
                select(Employee).where(
                    Employee.org_id == org_id, Employee.ist_aktiv.is_(True)
                )
            )
            .scalars()
            .all()
        )
        in_scope: list[dict[str, str]] = []
        no_contract: list[str] = []
        on_leave: list[str] = []
        for emp in employees:
            name = f"{emp.vorname} {emp.nachname}".strip()
            if is_on_leave(self.db, org_id=org_id, employee_id=emp.id, month=monat):
                on_leave.append(name)
                continue
            contract = get_aktiver_vertrag(self.db, emp.id, monat)
            if contract is None:
                no_contract.append(name)
                continue
            in_scope.append({"employee_id": emp.id, "employee_name": name})
        period = self._period(org_id, monat)
        return {
            "monat": monat.isoformat(),
            "label": f"{_MONTHS_DE[monat.month - 1]} {monat.year}",
            "locked": period is not None and period.status == PayrollPeriodStatus.LOCKED,
            "in_scope": in_scope,
            "in_scope_count": len(in_scope),
            "no_contract": no_contract,
            "on_leave": on_leave,
        }

    # ── I.6 on-leave list ──────────────────────────────────────────────────────
    def on_leave(self, org_id: str, fiscal_year_id: str, monat: date) -> list[dict[str, Any]]:
        monat = monat.replace(day=1)
        payrolls = (
            self.db.execute(
                select(MonthlyPayroll, Employee)
                .join(Employee, MonthlyPayroll.employee_id == Employee.id)
                .where(
                    MonthlyPayroll.org_id == org_id,
                    MonthlyPayroll.fiscal_year_id == fiscal_year_id,
                    MonthlyPayroll.monat == monat,
                    MonthlyPayroll.status == PayrollStatus.ON_LEAVE,
                )
            )
            .all()
        )
        out = []
        for _p, emp in payrolls:
            lp = self.db.execute(
                select(EmployeeLeavePeriod).where(
                    EmployeeLeavePeriod.org_id == org_id,
                    EmployeeLeavePeriod.employee_id == emp.id,
                    EmployeeLeavePeriod.start_date <= monat,
                )
            ).scalars().first()
            replacement = None
            if lp and lp.replacement:
                replacement = f"{lp.replacement.vorname} {lp.replacement.nachname}".strip()
            out.append({
                "employee_id": emp.id,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                "leave_type": lp.leave_type.value if lp else None,
                "expected_end_date": lp.expected_end_date.isoformat()
                if lp and lp.expected_end_date
                else None,
                "replacement_name": replacement,
            })
        return out

    # ── I.7 lock / reopen ──────────────────────────────────────────────────────
    def lock(
        self,
        org_id: str,
        fiscal_year_id: str,
        monat: date,
        *,
        locked_by: str | None = None,
    ) -> dict[str, Any]:
        monat = monat.replace(day=1)
        fy = self._fiscal_year(org_id, fiscal_year_id)
        if fy.status == FiscalYearStatus.GESCHLOSSEN:
            raise APIError(423, "FISCAL_YEAR_CLOSED", "Das Haushaltsjahr ist geschlossen.")
        period = self._period(org_id, monat)
        if period is None:
            period = PayrollPeriod(
                org_id=org_id, fiscal_year_id=fiscal_year_id, monat=monat,
                status=PayrollPeriodStatus.LOCKED,
            )
            self.db.add(period)
        else:
            period.status = PayrollPeriodStatus.LOCKED
        period.locked_at = datetime.now(UTC)
        period.locked_by = locked_by
        self.db.commit()
        return {"monat": monat.isoformat(), "status": "LOCKED"}

    def reopen(self, org_id: str, fiscal_year_id: str, monat: date) -> dict[str, Any]:
        monat = monat.replace(day=1)
        fy = self._fiscal_year(org_id, fiscal_year_id)
        if fy.status == FiscalYearStatus.GESCHLOSSEN:
            raise APIError(423, "FISCAL_YEAR_CLOSED", "Das Haushaltsjahr ist geschlossen.")
        period = self._period(org_id, monat)
        if period is not None:
            period.status = PayrollPeriodStatus.OPEN
            period.locked_at = None
            period.locked_by = None
            self.db.commit()
        return {"monat": monat.isoformat(), "status": "OPEN"}
