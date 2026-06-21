"""Bonus / adjustment computation (Module PCM, Areas G & H).

Pure-ish helpers that turn active salary adjustments, per-employee bonus
payments and matching org-level bonus templates into payroll detail-line specs
for one employee and month. Shared by the payroll engine (to write
``payroll_detail_lines`` and adjust brutto) and by the template eligibility
preview (G.3).

Brutto effect of a component, by brutto_type:
  EMPLOYER → AG-Brutto only · EMPLOYEE → AN- and AG-Brutto · NEITHER → fringe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import (
    AdjustmentType,
    BonusApplicableTo,
    BonusType,
    BruttoType,
    CostCenterTyp,
    PayrollDetailComponent,
)
from app.models.master import CostCenter
from app.models.payroll import Employee, EmployeeContract
from app.models.pcm_bonus import BonusPayment, BonusTemplate, SalaryAdjustment
from app.models.pcm_personnel import WochenstundenZuweisung
from app.services.pcm.calc import round2
from app.services.pcm.salary_tariff_service import _natural_key


@dataclass
class ComponentLine:
    component: PayrollDetailComponent
    description: str
    amount: Decimal  # signed (negative for deductions)
    brutto_type: BruttoType


def _active_in_month(period_from: date, period_to: date | None, month: date) -> bool:
    return period_from <= month and (period_to is None or period_to >= month)


def _employment_fraction(emp: Employee, month: date) -> float:
    """Share of the calendar year the employee was employed up to ``month``."""
    eintritt = emp.eintrittsdatum
    if eintritt.year < month.year:
        return 1.0
    if eintritt.year > month.year:
        return 0.0
    return max(0.0, (13 - eintritt.month) / 12.0)


def _amount_value(
    *,
    btype: BonusType,
    amount: Decimal,
    actual_salary: float,
    hours_prorated: bool,
    project_hours: float,
    standard_hours: float,
    prorate_employment: bool,
    employment_fraction: float,
) -> float:
    amt = float(amount)
    base = actual_salary * amt / 100.0 if btype in (
        BonusType.PERCENT,
        BonusType.REFERENCE_MONTH,
    ) else amt
    if hours_prorated and standard_hours > 0:
        base *= project_hours / standard_hours
    if prorate_employment:
        base *= employment_fraction
    return base


def template_matches(
    template: BonusTemplate,
    *,
    tariff_code: str | None,
    salary_group: str | None,
    has_project: bool,
    has_overhead: bool,
) -> bool:
    if template.tariff_code and template.tariff_code != tariff_code:
        return False
    if template.salary_group_min:
        if salary_group is None or _natural_key(salary_group) < _natural_key(
            template.salary_group_min
        ):
            return False
    if template.salary_group_max:
        if salary_group is None or _natural_key(salary_group) > _natural_key(
            template.salary_group_max
        ):
            return False
    if template.applicable_to == BonusApplicableTo.PROJECT_ONLY and not has_project:
        return False
    if template.applicable_to == BonusApplicableTo.OVERHEAD_ONLY and not has_overhead:
        return False
    return True


def _cost_center_flags(
    db: Session, assignments: list[WochenstundenZuweisung]
) -> tuple[bool, bool]:
    has_project = has_overhead = False
    for a in assignments:
        cc = db.get(CostCenter, a.cost_center_id)
        if cc is None:
            continue
        if cc.typ == CostCenterTyp.PROJECT:
            has_project = True
        elif cc.typ == CostCenterTyp.OVERHEAD:
            has_overhead = True
    return has_project, has_overhead


def compute_extra_components(
    db: Session,
    *,
    org_id: str,
    employee: Employee,
    contract: EmployeeContract,
    month: date,
    actual_salary: float,
    project_hours: float,
    standard_hours: float,
    assignments: list[WochenstundenZuweisung],
) -> list[ComponentLine]:
    """All bonus/adjustment detail lines for one employee-month (signed)."""
    lines: list[ComponentLine] = []
    employment_fraction = _employment_fraction(employee, month)

    def value(obj, btype: BonusType) -> float:
        return _amount_value(
            btype=btype,
            amount=obj.amount,
            actual_salary=actual_salary,
            hours_prorated=obj.proration_rule.value == "HOURS_PRORATED",
            project_hours=project_hours,
            standard_hours=standard_hours,
            prorate_employment=getattr(obj, "prorate_by_employment_period", False),
            employment_fraction=employment_fraction,
        )

    # ── salary adjustments (Area H) ────────────────────────────────────────────
    adjustments = (
        db.execute(
            select(SalaryAdjustment).where(
                SalaryAdjustment.org_id == org_id,
                SalaryAdjustment.employee_id == employee.id,
                SalaryAdjustment.period_from <= month,
                or_(
                    SalaryAdjustment.period_to.is_(None),
                    SalaryAdjustment.period_to >= month,
                ),
            )
        )
        .scalars()
        .all()
    )
    for adj in adjustments:
        raw = _amount_value(
            btype=BonusType.FIXED,
            amount=adj.amount,
            actual_salary=actual_salary,
            hours_prorated=adj.proration_rule == "HOURS_PRORATED",
            project_hours=project_hours,
            standard_hours=standard_hours,
            prorate_employment=False,
            employment_fraction=employment_fraction,
        )
        signed = -raw if adj.type == AdjustmentType.DEDUCTION else raw
        if adj.brutto_type == BruttoType.NEITHER:
            component = PayrollDetailComponent.FRINGE
        elif adj.type == AdjustmentType.DEDUCTION:
            component = PayrollDetailComponent.ADJUST_DED
        else:
            component = PayrollDetailComponent.ADJUST_ADD
        lines.append(
            ComponentLine(
                component=component,
                description=adj.description or "Anpassung",
                amount=round2(signed),
                brutto_type=adj.brutto_type,
            )
        )

    # ── per-employee bonus payments (Area H) ───────────────────────────────────
    payments = (
        db.execute(
            select(BonusPayment).where(
                BonusPayment.org_id == org_id,
                BonusPayment.employee_id == employee.id,
                BonusPayment.period_from <= month,
                or_(
                    BonusPayment.period_to.is_(None),
                    BonusPayment.period_to >= month,
                ),
            )
        )
        .scalars()
        .all()
    )
    manual_types: set[str] = set()
    for bp in payments:
        if bp.type == BonusType.REFERENCE_MONTH and bp.payment_month != month.month:
            continue
        manual_types.add(bp.type.value)
        comp = (
            PayrollDetailComponent.JSZ
            if bp.type == BonusType.REFERENCE_MONTH
            else PayrollDetailComponent.BONUS
        )
        lines.append(
            ComponentLine(
                component=comp,
                description=bp.description or "Bonus",
                amount=round2(value(bp, bp.type)),
                brutto_type=bp.brutto_type,
            )
        )

    # ── org-level bonus templates (Area G) ─────────────────────────────────────
    tariff_code = contract.salary_tariff.tariff_code if contract.salary_tariff else None
    salary_group = contract.entgeltgruppe
    has_project, has_overhead = _cost_center_flags(db, assignments)
    templates = (
        db.execute(
            select(BonusTemplate).where(
                BonusTemplate.org_id == org_id,
                BonusTemplate.period_from <= month,
                or_(
                    BonusTemplate.period_to.is_(None),
                    BonusTemplate.period_to >= month,
                ),
            )
        )
        .scalars()
        .all()
    )
    for tpl in templates:
        if tpl.type == BonusType.REFERENCE_MONTH and tpl.payment_month != month.month:
            continue
        # Per-employee record of the same type takes precedence over a template.
        if tpl.type.value in manual_types:
            continue
        if not template_matches(
            tpl,
            tariff_code=tariff_code,
            salary_group=salary_group,
            has_project=has_project,
            has_overhead=has_overhead,
        ):
            continue
        comp = (
            PayrollDetailComponent.JSZ
            if tpl.type == BonusType.REFERENCE_MONTH
            else PayrollDetailComponent.ZULAGE
        )
        lines.append(
            ComponentLine(
                component=comp,
                description=tpl.name,
                amount=round2(value(tpl, tpl.type)),
                brutto_type=tpl.brutto_type,
            )
        )

    return lines
