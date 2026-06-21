"""PCM payroll-run controllers — thin wrappers over the engine.

``run_one`` runs a single employee/month; ``run_monat`` runs every employee that
has an active hour assignment for the month (skipping, not failing, on per-employee
guard errors); ``detail_lines`` reads the itemized VWN breakdown for a payroll.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.payroll import MonthlyPayroll
from app.models.pcm_payroll import PayrollDetailLine
from app.models.pcm_personnel import WochenstundenZuweisung
from app.services.pcm._validate import parse_date, req_str
from app.services.pcm.payroll_engine import run_monthly_payroll
from app.services.personal.payroll_service import PayrollService
from app.utils.serialization import decimal_str


def _detail(line: PayrollDetailLine) -> dict[str, Any]:
    return {
        "id": line.id,
        "monthly_payroll_id": line.monthly_payroll_id,
        "component": str(line.component),
        "description": line.description,
        "amount": decimal_str(line.amount),
        "brutto_type": str(line.brutto_type),
        "source_record_id": line.source_record_id,
    }


class PcmPayrollService:
    def __init__(self, db: Session):
        self.db = db

    def run_one(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        employee_id = req_str(body, "employee_id")
        fiscal_year_id = req_str(body, "fiscal_year_id")
        monat = parse_date(body.get("monat"), "monat")
        payroll = run_monthly_payroll(
            self.db,
            org_id=org_id,
            employee_id=employee_id,
            fiscal_year_id=fiscal_year_id,
            monat=monat,
        )
        # Reuse the existing payroll serialization (incl. allocations).
        return PayrollService(self.db).get(org_id, payroll.id)

    def run_monat(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        fiscal_year_id = req_str(body, "fiscal_year_id")
        monat = parse_date(body.get("monat"), "monat")

        employee_ids = (
            self.db.execute(
                select(WochenstundenZuweisung.employee_id)
                .where(
                    WochenstundenZuweisung.org_id == org_id,
                    WochenstundenZuweisung.effective_date <= monat,
                    or_(
                        WochenstundenZuweisung.end_date.is_(None),
                        WochenstundenZuweisung.end_date >= monat,
                    ),
                )
                .distinct()
            )
            .scalars()
            .all()
        )

        run: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for eid in employee_ids:
            try:
                payroll = run_monthly_payroll(
                    self.db,
                    org_id=org_id,
                    employee_id=eid,
                    fiscal_year_id=fiscal_year_id,
                    monat=monat,
                )
                run.append({"employee_id": eid, "payroll_id": payroll.id})
            except APIError as exc:
                # Clear any pending state and continue with the next employee.
                self.db.rollback()
                skipped.append(
                    {"employee_id": eid, "code": exc.code, "message": exc.message}
                )

        return {
            "monat": monat.isoformat(),
            "fiscal_year_id": fiscal_year_id,
            "run_count": len(run),
            "skipped_count": len(skipped),
            "run": run,
            "skipped": skipped,
        }

    def detail_lines(self, org_id: str, payroll_id: str) -> list[dict[str, Any]]:
        payroll = self.db.execute(
            select(MonthlyPayroll).where(
                MonthlyPayroll.id == payroll_id, MonthlyPayroll.org_id == org_id
            )
        ).scalar_one_or_none()
        if payroll is None:
            raise APIError(404, "NOT_FOUND", "Abrechnung nicht gefunden.")
        lines = (
            self.db.execute(
                select(PayrollDetailLine)
                .where(PayrollDetailLine.monthly_payroll_id == payroll_id)
                .order_by(PayrollDetailLine.component)
            )
            .scalars()
            .all()
        )
        return [_detail(line) for line in lines]
