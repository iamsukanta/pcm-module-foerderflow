"""Personnel cost forecast engine (Module PCM, Area K).

Projects each active employee's monthly personnel cost across a fiscal year,
reusing the payroll machinery: tariff validity-window resolution (with proposed
fallback), Stufenaufstieg, the Dreisatz, BAV, and the bonus/adjustment engine.
ON_LEAVE months are suppressed to zero; data-quality issues are flagged per row
(MISSING / DATA_GAP / PROPOSED_TARIFF).

Forecast rows for a fiscal year are fully replaced on each run.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import BruttoType, FiscalYearStatus, PayrollDetailComponent
from app.models.master import FiscalYear
from app.models.organization import Organization
from app.models.payroll import Employee
from app.models.pcm_forecast import PersonalCostForecast
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryLevel
from app.services.pcm.bonus_engine import compute_extra_components
from app.services.pcm.calc import compute_bav, round2
from app.services.pcm.leave_service import is_on_leave
from app.services.pcm.tariff_lookup import resolve_tariff
from app.services.personal.berechnung import (
    berechne_gehalt,
    get_ag_faktor,
    get_aktiver_vertrag,
)


def _months(fy: FiscalYear) -> list[date]:
    out, cur = [], fy.beginn.replace(day=1)
    while cur <= fy.ende:
        out.append(cur)
        cur = cur + relativedelta(months=1)
    return out


def _forecast_level(db: Session, org_id: str, contract, month: date) -> int | None:
    """Current tier at ``month`` accounting for a single Stufenaufstieg."""
    level = contract.stufe
    if level is None or contract.salary_tariff is None or not contract.entgeltgruppe:
        return level
    level_row = db.execute(
        select(SalaryLevel).where(
            SalaryLevel.org_id == org_id,
            SalaryLevel.tariff_id == contract.salary_tariff_id,
            SalaryLevel.salary_group == contract.entgeltgruppe,
            SalaryLevel.level_no == level,
        )
    ).scalar_one_or_none()
    if level_row is None or level_row.months_to_next_level is None:
        return level
    promo = contract.next_level_date or contract.gueltig_ab + relativedelta(
        months=level_row.months_to_next_level
    )
    return level + 1 if month >= promo else level


def run_forecast(
    db: Session,
    org_id: str,
    fiscal_year_id: str,
    *,
    include_proposed: bool = True,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fy = db.get(FiscalYear, fiscal_year_id)
    if fy is None or fy.org_id != org_id:
        raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")
    if fy.status == FiscalYearStatus.GESCHLOSSEN:
        raise APIError(423, "FISCAL_YEAR_CLOSED", "Das Haushaltsjahr ist geschlossen.")

    db.execute(
        delete(PersonalCostForecast).where(
            PersonalCostForecast.org_id == org_id,
            PersonalCostForecast.fiscal_year_id == fiscal_year_id,
        )
    )
    org = db.get(Organization, org_id)
    run_at = datetime.now(UTC)
    months = _months(fy)
    employees = (
        db.execute(
            select(Employee).where(
                Employee.org_id == org_id, Employee.ist_aktiv.is_(True)
            )
        )
        .scalars()
        .all()
    )

    row_count = 0
    warnings: dict[str, int] = {}
    for emp in employees:
        for month in months:
            row = _forecast_one(
                db, org=org, org_id=org_id, fy_id=fiscal_year_id, emp=emp,
                month=month, run_at=run_at, include_proposed=include_proposed,
                override=(overrides or {}).get(emp.id),
            )
            if row is None:
                continue
            db.add(row)
            row_count += 1
            if row.warning:
                warnings[row.warning] = warnings.get(row.warning, 0) + 1

    db.commit()
    return {
        "fiscal_year_id": fiscal_year_id,
        "employee_count": len(employees),
        "month_count": len(months),
        "row_count": row_count,
        "warnings": warnings,
        "forecast_run_at": run_at.isoformat(),
    }


def _forecast_one(
    db, *, org, org_id, fy_id, emp, month, run_at, include_proposed, override=None
) -> PersonalCostForecast | None:
    contract = get_aktiver_vertrag(db, emp.id, month)
    if contract is None:
        return None  # not employed this month

    if is_on_leave(db, org_id=org_id, employee_id=emp.id, month=month):
        return PersonalCostForecast(
            org_id=org_id, fiscal_year_id=fy_id, employee_id=emp.id, monat=month,
            forecast_level=contract.stufe, forecast_salary=Decimal("0.00"),
            standard_hours=Decimal("0.00"), forecast_hours=Decimal("0.00"),
            prorated_salary=Decimal("0.00"), an_brutto=Decimal("0.00"),
            ag_brutto=Decimal("0.00"), bav_amount=Decimal("0.00"),
            fringe_amount=Decimal("0.00"), total_forecast=Decimal("0.00"),
            warning="ON_LEAVE", components=[], forecast_run_at=run_at,
        )

    level = _forecast_level(db, org_id, contract, month)
    if override and override.get("level") is not None:
        level = int(override["level"])  # scenario level override
    warning: str | None = None

    # Base salary + standard hours via tariff window (proposed fallback), else
    # the contract's own base + org regular hours.
    base_full_time = float(contract.base_salary)
    standard_hours = float(org.regelarbeitszeit_stunden)
    bav_rate = float(org.bav_rate_pct or 0)  # org default
    if contract.salary_tariff is not None and contract.entgeltgruppe:
        tariff = resolve_tariff(
            db, org_id=org_id, tariff_code=contract.salary_tariff.tariff_code,
            salary_group=contract.entgeltgruppe, level=level, month=month,
        )
        if tariff is None:
            warning = "DATA_GAP"
        else:
            base_full_time = float(tariff.monthly_amount)
            standard_hours = float(tariff.standard_hours)
            bav_rate = (
                float(tariff.bav_rate_pct)
                if tariff.bav_rate_pct is not None
                else float(org.bav_rate_pct or 0)
            )
            if tariff.is_proposed:
                warning = "PROPOSED_TARIFF" if include_proposed else "DATA_GAP"

    # Scenario: global tariff growth-rate uplift on the full-time base.
    if override and override.get("growth_pct"):
        base_full_time *= 1.0 + float(override["growth_pct"]) / 100.0

    assignments = (
        db.execute(
            select(WochenstundenZuweisung).where(
                WochenstundenZuweisung.org_id == org_id,
                WochenstundenZuweisung.employee_id == emp.id,
                WochenstundenZuweisung.effective_date <= month,
                or_(
                    WochenstundenZuweisung.end_date.is_(None),
                    WochenstundenZuweisung.end_date >= month,
                ),
            )
        )
        .scalars()
        .all()
    )
    if assignments:
        project_hours = sum(float(a.weekly_hours) for a in assignments)
    else:
        project_hours = float(contract.assigned_hours)
        warning = warning or "MISSING"
    if override and override.get("hours") is not None:
        project_hours = float(override["hours"])  # scenario hour override

    vertragsart = (
        contract.vertragsart.value
        if hasattr(contract.vertragsart, "value")
        else contract.vertragsart
    )
    ag_faktor = get_ag_faktor(db, org_id, vertragsart, month)
    calc = berechne_gehalt(
        base_salary=base_full_time, assigned_hours=project_hours,
        standard_hours=standard_hours, ag_faktor=ag_faktor, components=[],
    )
    bav_amount = compute_bav(actual_salary=calc.actual_salary, bav_rate_pct=bav_rate)
    an_brutto = calc.an_brutto
    ag_brutto = calc.ag_brutto + bav_amount

    components: list[dict[str, Any]] = [
        {"component": PayrollDetailComponent.BASE.value, "description": "Grundgehalt (anteilig)",
         "amount": str(round2(calc.actual_salary)), "brutto_type": BruttoType.EMPLOYER.value},
    ]
    if bav_amount > 0:
        components.append({"component": PayrollDetailComponent.BAV.value,
                           "description": f"BAV {bav_rate:.2f}%", "amount": str(round2(bav_amount)),
                           "brutto_type": BruttoType.EMPLOYER.value})

    extra = compute_extra_components(
        db, org_id=org_id, employee=emp, contract=contract, month=month,
        actual_salary=calc.actual_salary, project_hours=project_hours,
        standard_hours=standard_hours, assignments=assignments,
    )
    fringe = 0.0
    for line in extra:
        amt = float(line.amount)
        if line.brutto_type == BruttoType.EMPLOYER:
            ag_brutto += amt
        elif line.brutto_type == BruttoType.EMPLOYEE:
            an_brutto += amt
            ag_brutto += amt
        else:
            fringe += amt
        components.append({"component": line.component.value, "description": line.description,
                           "amount": str(line.amount), "brutto_type": line.brutto_type.value})

    total = ag_brutto + fringe
    return PersonalCostForecast(
        org_id=org_id, fiscal_year_id=fy_id, employee_id=emp.id, monat=month,
        forecast_level=level, forecast_salary=round2(base_full_time),
        standard_hours=round2(standard_hours), forecast_hours=round2(project_hours),
        prorated_salary=round2(calc.actual_salary), an_brutto=round2(an_brutto),
        ag_brutto=round2(ag_brutto), bav_amount=round2(bav_amount),
        fringe_amount=round2(fringe), total_forecast=round2(total),
        warning=warning, components=components, forecast_run_at=run_at,
    )
