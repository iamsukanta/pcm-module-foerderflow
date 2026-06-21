"""Salary-tariff validity-window resolution + overlap validation (Module PCM).

A ``salary_tariffs`` row is active for a month when
``valid_from <= month <= valid_to`` (null ``valid_to`` = open-ended). The forecast
and payroll engines select the active *current* (``is_proposed = false``) row for a
month, falling back to a *proposed* row only if no current row covers the month —
this is what makes a mid-year tariff split work automatically.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import FiscalYearStatus
from app.models.master import FiscalYear
from app.models.pcm_tariff import SalaryTariff

# Sentinel for an open-ended (null valid_to) window in interval math.
_OPEN_END = date.max


def assert_fiscal_year_open(db: Session, *, org_id: str, on: date) -> None:
    """Fiscal-year write-gate (Tariff Registry DevGuide §6.2).

    If a fiscal year covers ``on`` and is CLOSED (GESCHLOSSEN), block the write
    with ``423 Locked``. If no fiscal year covers the date, the write is allowed
    (an org may enter tariff data before defining the year).
    """
    fy = (
        db.execute(
            select(FiscalYear).where(
                FiscalYear.org_id == org_id,
                FiscalYear.beginn <= on,
                FiscalYear.ende >= on,
            )
        )
        .scalars()
        .first()
    )
    if fy is not None and fy.status == FiscalYearStatus.GESCHLOSSEN:
        raise APIError(
            423,
            "FISCAL_YEAR_CLOSED",
            "Das Geschäftsjahr ist abgeschlossen. Tarif-Änderungen für diesen "
            "Zeitraum sind nicht zulässig.",
            extra={"fiscal_year_id": fy.id, "jahr": fy.jahr},
        )


def resolve_tariff(
    db: Session,
    *,
    org_id: str,
    tariff_code: str,
    salary_group: str,
    level: int,
    month: date,
) -> SalaryTariff | None:
    """Return the tariff row active for ``month``.

    Current rows win over proposed rows. Among rows of the same kind, the one with
    the latest ``valid_from`` that still covers the month is chosen. Returns
    ``None`` if neither a current nor a proposed row covers the month (a coverage
    gap the caller treats as a DATA GAP).
    """
    for is_proposed in (False, True):
        row = (
            db.execute(
                select(SalaryTariff)
                .where(
                    SalaryTariff.org_id == org_id,
                    SalaryTariff.tariff_code == tariff_code,
                    SalaryTariff.salary_group == salary_group,
                    SalaryTariff.level == level,
                    SalaryTariff.is_proposed.is_(is_proposed),
                    SalaryTariff.deleted_at.is_(None),
                    SalaryTariff.valid_from <= month,
                    or_(
                        SalaryTariff.valid_to.is_(None),
                        SalaryTariff.valid_to >= month,
                    ),
                )
                .order_by(SalaryTariff.valid_from.desc())
            )
            .scalars()
            .first()
        )
        if row is not None:
            return row
    return None


def assert_window_valid(valid_from: date, valid_to: date | None) -> None:
    """Reject a zero/negative-length validity window."""
    if valid_to is not None and valid_to < valid_from:
        raise APIError(
            422,
            "TARIFF_WINDOW_INVALID",
            "valid_to darf nicht vor valid_from liegen.",
        )


def assert_no_overlap(
    db: Session,
    *,
    org_id: str,
    tariff_code: str,
    salary_group: str,
    level: int,
    is_proposed: bool,
    valid_from: date,
    valid_to: date | None,
    exclude_id: str | None = None,
) -> None:
    """Guard the no-overlap rule for a (proposed) tariff key.

    Two rows of the same ``(org, tariff_code, salary_group, level, is_proposed)``
    may not have overlapping validity windows — otherwise the per-month lookup
    would be ambiguous. Raises ``APIError(409)`` on conflict.
    """
    assert_window_valid(valid_from, valid_to)
    new_to = valid_to or _OPEN_END

    existing = (
        db.execute(
            select(SalaryTariff).where(
                SalaryTariff.org_id == org_id,
                SalaryTariff.tariff_code == tariff_code,
                SalaryTariff.salary_group == salary_group,
                SalaryTariff.level == level,
                SalaryTariff.is_proposed.is_(is_proposed),
                SalaryTariff.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    for row in existing:
        if exclude_id is not None and row.id == exclude_id:
            continue
        row_to = row.valid_to or _OPEN_END
        # Half-open interval overlap test on closed date ranges.
        if row.valid_from <= new_to and row_to >= valid_from:
            raise APIError(
                409,
                "TARIFF_WINDOW_OVERLAP",
                "Das Gültigkeitsfenster überschneidet sich mit einem bestehenden "
                f"Tarif-Eintrag ({row.valid_from} – {row.valid_to or 'offen'}).",
                extra={"conflict_id": row.id},
            )
