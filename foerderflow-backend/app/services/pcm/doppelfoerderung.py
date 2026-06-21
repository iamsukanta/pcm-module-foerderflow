"""Doppelförderungs guard — a hard save-block at Wochenstundenzuweisung entry.

An employee's working time may not be financed beyond its capacity:

- ``ACTUAL_HOURS`` contracts: the sum of weekly hours across all active
  assignments must not exceed the contracted weekly hours.
- ``PLAN_PERCENTAGE`` contracts: the sum of plan percentages must not exceed 100,
  and every linked funding measure must permit plan-based allocation
  (``funding_measures.allows_plan_based_allocation = true``).

No role bypasses this check (per §2.5). Raising ``APIError`` here means routes get
a clean 409/422 envelope.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import AllocationMethod
from app.models.funding import FundingMeasure
from app.models.payroll import EmployeeContract
from app.models.pcm_personnel import WochenstundenZuweisung

# Float tolerance for hour/percentage sums (mirrors the allocation invariant).
_EPS = 0.01


def _active_assignments(
    db: Session,
    *,
    org_id: str,
    employee_id: str,
    on_or_after: date,
    exclude_id: str | None,
) -> list[WochenstundenZuweisung]:
    rows = (
        db.execute(
            select(WochenstundenZuweisung).where(
                WochenstundenZuweisung.org_id == org_id,
                WochenstundenZuweisung.employee_id == employee_id,
                or_(
                    WochenstundenZuweisung.end_date.is_(None),
                    WochenstundenZuweisung.end_date >= on_or_after,
                ),
            )
        )
        .scalars()
        .all()
    )
    return [r for r in rows if exclude_id is None or r.id != exclude_id]


def assert_assignment_allowed(
    db: Session,
    *,
    org_id: str,
    contract: EmployeeContract,
    new_weekly_hours: float,
    effective_date: date,
    funding_measure_id: str | None = None,
    exclude_id: str | None = None,
) -> None:
    """Validate that adding ``new_weekly_hours`` keeps the employee within capacity.

    ``exclude_id`` lets an *update* ignore the assignment being edited. Raises
    ``APIError`` on violation; returns ``None`` when the assignment is allowed.
    """
    existing = _active_assignments(
        db,
        org_id=org_id,
        employee_id=contract.employee_id,
        on_or_after=effective_date,
        exclude_id=exclude_id,
    )
    total = sum(float(a.weekly_hours) for a in existing) + float(new_weekly_hours)

    if contract.allocation_method == AllocationMethod.PLAN_PERCENTAGE:
        if funding_measure_id is not None:
            measure = db.get(FundingMeasure, funding_measure_id)
            if measure is None or not measure.allows_plan_based_allocation:
                raise APIError(
                    422,
                    "PLAN_ALLOCATION_NOT_PERMITTED",
                    "Planbasierte Zuordnung ist für diese Fördermaßnahme nicht "
                    "freigegeben (allows_plan_based_allocation = false).",
                )
        if total - 100.0 > _EPS:
            raise APIError(
                409,
                "PLAN_PERCENT_EXCEEDED",
                "Die Summe der Plan-Prozentsätze darf 100 % nicht überschreiten. "
                f"Aktuell: {total:.2f} %.",
                extra={"total_percent": round(total, 2)},
            )
        return

    contracted = float(contract.assigned_hours)
    if total - contracted > _EPS:
        raise APIError(
            409,
            "DOPPELFOERDERUNG",
            "Die zugewiesenen Wochenstunden überschreiten die vertraglich "
            f"vereinbarten Stunden ({total:.2f} h > {contracted:.2f} h).",
            extra={"total_hours": round(total, 2), "contracted_hours": contracted},
        )
