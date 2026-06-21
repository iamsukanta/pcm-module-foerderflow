"""Promotion Job — automatic Stufenaufstieg (Module PCM, US-PCM-04 / DevGuide §8).

Advances every active contract whose time-in-tier threshold has been reached:
closes the current contract, opens a new one at level + 1 with the next tier's
salary, and writes an AUTO_PROMOTION audit entry. Employees on active leave or at
the maximum tier are skipped. Designed to run nightly, but also triggerable on
demand from the Progression dashboard.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AuditActionType
from app.models.payroll import Employee, EmployeeContract
from app.models.pcm_tariff import SalaryLevel
from app.services.pcm.audit_service import log_assignment_change
from app.services.pcm.leave_service import is_on_leave
from app.utils.serialization import decimal_str


def run_promotions(
    db: Session,
    org_id: str,
    *,
    as_of: date | None = None,
    changed_by: str | None = None,
) -> dict[str, Any]:
    today = as_of or date.today()
    contracts = (
        db.execute(
            select(EmployeeContract, Employee)
            .join(Employee, EmployeeContract.employee_id == Employee.id)
            .where(
                EmployeeContract.org_id == org_id,
                EmployeeContract.salary_tariff_id.is_not(None),
                EmployeeContract.entgeltgruppe.is_not(None),
                EmployeeContract.stufe.is_not(None),
                Employee.ist_aktiv.is_(True),
            )
        )
        .all()
    )

    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for contract, emp in contracts:
        if contract.gueltig_bis is not None and contract.gueltig_bis < today:
            continue  # not the open contract
        tariff = contract.salary_tariff
        if tariff is None or tariff.deleted_at is not None:
            continue
        level_row = db.execute(
            select(SalaryLevel).where(
                SalaryLevel.org_id == org_id,
                SalaryLevel.tariff_id == tariff.id,
                SalaryLevel.salary_group == contract.entgeltgruppe,
                SalaryLevel.level_no == contract.stufe,
            )
        ).scalar_one_or_none()
        if level_row is None or level_row.months_to_next_level is None:
            continue  # no rule / maximum tier

        if contract.next_level_date is not None:
            promotion_date = contract.next_level_date
        else:
            promotion_date = contract.gueltig_ab + relativedelta(
                months=level_row.months_to_next_level
            )
        if promotion_date > today:
            continue  # not yet due

        if is_on_leave(
            db, org_id=org_id, employee_id=emp.id, month=promotion_date.replace(day=1)
        ):
            skipped.append({
                "employee_id": emp.id,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                "code": "ON_LEAVE",
                "message": "Während aktiver Abwesenheit kein Aufstieg.",
            })
            continue

        next_level_row = db.execute(
            select(SalaryLevel).where(
                SalaryLevel.org_id == org_id,
                SalaryLevel.tariff_id == tariff.id,
                SalaryLevel.salary_group == contract.entgeltgruppe,
                SalaryLevel.level_no == contract.stufe + 1,
            )
        ).scalar_one_or_none()
        if next_level_row is None:
            skipped.append({
                "employee_id": emp.id,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                "code": "NO_NEXT_LEVEL",
                "message": f"Keine Tarifdaten für {contract.entgeltgruppe} "
                           f"Stufe {contract.stufe + 1}.",
            })
            continue

        old_level = contract.stufe
        old_amount = contract.base_salary
        contract.gueltig_bis = promotion_date - timedelta(days=1)
        new_contract = EmployeeContract(
            org_id=org_id,
            employee_id=emp.id,
            vertragsart=contract.vertragsart,
            assigned_hours=contract.assigned_hours,
            base_salary=next_level_row.monthly_amount,
            tarifwerk=contract.tarifwerk,
            entgeltgruppe=contract.entgeltgruppe,
            stufe=old_level + 1,
            gueltig_ab=promotion_date,
            allocation_method=contract.allocation_method,
            salary_tariff_id=contract.salary_tariff_id,
        )
        db.add(new_contract)
        db.flush()
        log_assignment_change(
            db,
            org_id=org_id,
            employee_id=emp.id,
            action_type=AuditActionType.AUTO_PROMOTION,
            salary_assignment_id=new_contract.id,
            summary=(
                f"Stufenaufstieg: {contract.entgeltgruppe} Stufe "
                f"{old_level} → {old_level + 1} ab {promotion_date.isoformat()}"
            ),
            old_values={"level": old_level, "base_salary": decimal_str(old_amount)},
            new_values={
                "level": old_level + 1,
                "base_salary": decimal_str(next_level_row.monthly_amount),
            },
            changed_by=changed_by or "Promotion-Job",
        )
        promoted.append({
            "employee_id": emp.id,
            "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
            "salary_group": contract.entgeltgruppe,
            "from_level": old_level,
            "to_level": old_level + 1,
            "promotion_date": promotion_date.isoformat(),
            "new_amount": decimal_str(next_level_row.monthly_amount),
        })

    db.commit()
    return {
        "promoted": promoted,
        "skipped": skipped,
        "promoted_count": len(promoted),
        "skipped_count": len(skipped),
        "as_of": today.isoformat(),
    }
