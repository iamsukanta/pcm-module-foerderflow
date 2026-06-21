"""Module PCM Phase-2 engine tests: tariff validity-window resolution, the
Doppelförderungs guard, and the monthly payroll run (Dreisatz + BAV + detail
lines + PCM allocations), including mid-year tariff split, re-run safety, and the
fiscal-year / edge-case guards.

Uses the sync SQLite harness (conftest ``db_session`` + ``org``)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import APIError
from app.models.enums import (
    AllocationMethod,
    AllocationOrigin,
    CostCenterTyp,
    FiscalYearStatus,
    FunderTyp,
    MittelabrufVerfahren,
    PayrollStatus,
    Vertragsart,
)
from app.models.funding import FundingMeasure
from app.models.master import CostCenter, FiscalYear, Funder
from app.models.payroll import (
    Employee,
    EmployeeContract,
    EmployerGrossFactor,
    MonthlyPayroll,
)
from app.models.pcm_payroll import PayrollDetailLine
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryTariff
from app.services.pcm import (
    assert_assignment_allowed,
    assert_no_overlap,
    assert_window_valid,
    resolve_tariff,
    run_monthly_payroll,
)

JAN = date(2026, 1, 1)
MAY = date(2026, 5, 1)


# ── builders ──────────────────────────────────────────────────────────────────
def _fy(db, org, *, jahr=2026, status=FiscalYearStatus.OFFEN) -> FiscalYear:
    fy = FiscalYear(
        org_id=org.id,
        jahr=jahr,
        beginn=date(jahr, 1, 1),
        ende=date(jahr, 12, 31),
        status=status,
    )
    db.add(fy)
    db.commit()
    db.refresh(fy)
    return fy


def _cc(db, org, code="P1") -> CostCenter:
    c = CostCenter(
        org_id=org.id, code=code, name=f"Projekt {code}",
        typ=CostCenterTyp.PROJECT, ist_aktiv=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _employee(db, org, code="EMP1") -> Employee:
    e = Employee(
        org_id=org.id, employee_code=code, vorname="Anna", nachname="Beispiel",
        eintrittsdatum=JAN, ist_aktiv=True,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _contract(
    db, org, emp, *, assigned_hours=39, base=4000,
    method=AllocationMethod.ACTUAL_HOURS, tariff_id=None, gueltig_ab=JAN,
) -> EmployeeContract:
    c = EmployeeContract(
        org_id=org.id, employee_id=emp.id, vertragsart=Vertragsart.FESTANSTELLUNG,
        assigned_hours=Decimal(str(assigned_hours)), base_salary=Decimal(str(base)),
        gueltig_ab=gueltig_ab, allocation_method=method, salary_tariff_id=tariff_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _tariff(
    db, org, *, group="E10", level=3, amount, vfrom, vto,
    proposed=False, bav=Decimal("4.70"),
) -> SalaryTariff:
    t = SalaryTariff(
        org_id=org.id, tariff_code="TVöD-VKA", salary_group=group, level=level,
        monthly_amount=Decimal(str(amount)), standard_hours=Decimal("39.00"),
        is_proposed=proposed, valid_from=vfrom, valid_to=vto, bav_rate_pct=bav,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _wsz(db, org, emp, contract, cc, *, hours, effective=JAN, end=None, fm=None):
    w = WochenstundenZuweisung(
        org_id=org.id, employee_id=emp.id, salary_assignment_id=contract.id,
        cost_center_id=cc.id, funding_measure_id=fm,
        weekly_hours=Decimal(str(hours)), effective_date=effective, end_date=end,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def _gross_factor(db, org, faktor="1.2000") -> None:
    db.add(EmployerGrossFactor(
        org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
        faktor=Decimal(faktor), gueltig_ab=JAN,
    ))
    db.commit()


def _measure(db, org, *, allows_plan) -> FundingMeasure:
    funder = Funder(org_id=org.id, name="Funder", typ=FunderTyp.STIFTUNG)
    db.add(funder)
    db.commit()
    db.refresh(funder)
    m = FundingMeasure(
        org_id=org.id, funder_id=funder.id, name="Maßnahme",
        budget_gesamt=Decimal("10000"), foerderquote=Decimal("80"),
        laufzeit_von=JAN, laufzeit_bis=date(2026, 12, 31),
        mittelabruf_verfahren=MittelabrufVerfahren.ANFORDERUNG,
        allows_plan_based_allocation=allows_plan,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _split(db, org, *, group="E10", level=3, bav=Decimal("4.70")):
    """Two non-overlapping windows = a mid-year tariff change. Returns the Jan row."""
    jan = _tariff(db, org, group=group, level=level, amount=4500,
                  vfrom=JAN, vto=date(2026, 4, 30), bav=bav)
    _tariff(db, org, group=group, level=level, amount=4650,
            vfrom=MAY, vto=None, bav=bav)
    return jan


# ── tariff validity-window resolution ─────────────────────────────────────────
def test_resolve_tariff_midyear_split(db_session, org):
    _split(db_session, org)
    jan = resolve_tariff(db_session, org_id=org.id, tariff_code="TVöD-VKA",
                         salary_group="E10", level=3, month=JAN)
    may = resolve_tariff(db_session, org_id=org.id, tariff_code="TVöD-VKA",
                         salary_group="E10", level=3, month=MAY)
    dec = resolve_tariff(db_session, org_id=org.id, tariff_code="TVöD-VKA",
                         salary_group="E10", level=3, month=date(2026, 12, 1))
    assert jan.monthly_amount == Decimal("4500.00")
    assert may.monthly_amount == Decimal("4650.00")
    assert dec.monthly_amount == Decimal("4650.00")  # open-ended May row


def test_resolve_tariff_current_preferred_over_proposed(db_session, org):
    _tariff(db_session, org, amount=4500, vfrom=JAN, vto=None, proposed=False)
    _tariff(db_session, org, amount=9999, vfrom=JAN, vto=None, proposed=True)
    row = resolve_tariff(db_session, org_id=org.id, tariff_code="TVöD-VKA",
                         salary_group="E10", level=3, month=JAN)
    assert row.monthly_amount == Decimal("4500.00")
    assert row.is_proposed is False


def test_resolve_tariff_proposed_fallback_and_gap(db_session, org):
    # Only a proposed row covering Jan → returned as fallback.
    _tariff(db_session, org, amount=4800, vfrom=JAN, vto=None, proposed=True)
    fallback = resolve_tariff(db_session, org_id=org.id, tariff_code="TVöD-VKA",
                              salary_group="E10", level=3, month=JAN)
    assert fallback is not None and fallback.is_proposed is True
    # A month before any window → coverage gap → None.
    gap = resolve_tariff(db_session, org_id=org.id, tariff_code="TVöD-VKA",
                         salary_group="E10", level=3, month=date(2025, 12, 1))
    assert gap is None


def test_assert_no_overlap(db_session, org):
    _tariff(db_session, org, amount=4500, vfrom=JAN, vto=date(2026, 4, 30))
    # Overlapping window → raises.
    with pytest.raises(APIError) as ei:
        assert_no_overlap(
            db_session, org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10",
            level=3, is_proposed=False, valid_from=date(2026, 4, 15), valid_to=MAY,
        )
    assert ei.value.code == "TARIFF_WINDOW_OVERLAP"
    # Adjacent, non-overlapping window → allowed.
    assert_no_overlap(
        db_session, org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10",
        level=3, is_proposed=False, valid_from=MAY, valid_to=None,
    )


def test_assert_window_valid_rejects_reversed():
    with pytest.raises(APIError) as ei:
        assert_window_valid(MAY, JAN)
    assert ei.value.code == "TARIFF_WINDOW_INVALID"


# ── Doppelförderungs guard ────────────────────────────────────────────────────
def test_doppelfoerderung_blocks_over_hours(db_session, org):
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp, assigned_hours=39)
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=30)
    with pytest.raises(APIError) as ei:
        assert_assignment_allowed(
            db_session, org_id=org.id, contract=contract,
            new_weekly_hours=15, effective_date=JAN,
        )
    assert ei.value.code == "DOPPELFOERDERUNG"
    # 30 + 9 = 39 ≤ 39 → allowed.
    assert_assignment_allowed(
        db_session, org_id=org.id, contract=contract,
        new_weekly_hours=9, effective_date=JAN,
    )


def test_plan_percentage_requires_permission(db_session, org):
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp, method=AllocationMethod.PLAN_PERCENTAGE)
    not_allowed = _measure(db_session, org, allows_plan=False)
    with pytest.raises(APIError) as ei:
        assert_assignment_allowed(
            db_session, org_id=org.id, contract=contract, new_weekly_hours=50,
            effective_date=JAN, funding_measure_id=not_allowed.id,
        )
    assert ei.value.code == "PLAN_ALLOCATION_NOT_PERMITTED"

    allowed = _measure(db_session, org, allows_plan=True)
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=70, fm=allowed.id)
    with pytest.raises(APIError) as ei2:
        assert_assignment_allowed(
            db_session, org_id=org.id, contract=contract, new_weekly_hours=40,
            effective_date=JAN, funding_measure_id=allowed.id,
        )
    assert ei2.value.code == "PLAN_PERCENT_EXCEEDED"


# ── monthly payroll engine ────────────────────────────────────────────────────
def _detail_components(db, payroll_id) -> set[str]:
    rows = db.execute(
        select(PayrollDetailLine).where(
            PayrollDetailLine.monthly_payroll_id == payroll_id
        )
    ).scalars().all()
    return {str(r.component) for r in rows}


def test_run_monthly_payroll_basic(db_session, org):
    _gross_factor(db_session, org)  # ag_faktor = 1.2
    fy = _fy(db_session, org)
    jan_tariff = _split(db_session, org)
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp, assigned_hours=39, tariff_id=jan_tariff.id)
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=39)

    p = run_monthly_payroll(
        db_session, org_id=org.id, employee_id=emp.id,
        fiscal_year_id=fy.id, monat=JAN,
    )
    # Dreisatz: 4500 × 39/39 = 4500; AG = 4500 × 1.2 = 5400; BAV = 4500 × 4.7% = 211.50.
    assert p.quelle == "PCM"
    assert p.status == PayrollStatus.CALCULATED
    assert p.base_salary == Decimal("4500.00")
    assert p.actual_salary == Decimal("4500.00")
    assert p.betrag_an_brutto == Decimal("4500.00")
    assert p.bav_amount == Decimal("211.50")
    assert p.betrag_ag_brutto == Decimal("5611.50")  # 5400 + 211.50

    assert _detail_components(db_session, p.id) == {"BASE", "BAV"}

    allocs = db_session.execute(
        select(MonthlyPayroll).where(MonthlyPayroll.id == p.id)
    ).scalar_one().allocations
    assert len(allocs) == 1
    assert allocs[0].origin == AllocationOrigin.PCM
    assert allocs[0].prozent == Decimal("100.00")
    assert allocs[0].betrag_anteil == Decimal("5611.50")


def test_run_monthly_payroll_midyear_split(db_session, org):
    _gross_factor(db_session, org)
    fy = _fy(db_session, org)
    jan_tariff = _split(db_session, org)
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp, tariff_id=jan_tariff.id)
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=39)

    p_may = run_monthly_payroll(
        db_session, org_id=org.id, employee_id=emp.id,
        fiscal_year_id=fy.id, monat=MAY,
    )
    # May picks the 4650 window automatically.
    assert p_may.base_salary == Decimal("4650.00")
    assert p_may.actual_salary == Decimal("4650.00")
    assert p_may.bav_amount == Decimal("218.55")  # 4650 × 4.7%
    assert p_may.betrag_ag_brutto == Decimal("5798.55")  # 4650×1.2 + 218.55


def test_run_monthly_payroll_split_allocations(db_session, org):
    _gross_factor(db_session, org)
    fy = _fy(db_session, org)
    jan_tariff = _split(db_session, org)
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp, assigned_hours=39, tariff_id=jan_tariff.id)
    cc1 = _cc(db_session, org, "P1")
    cc2 = _cc(db_session, org, "P2")
    _wsz(db_session, org, emp, contract, cc1, hours=20)
    _wsz(db_session, org, emp, contract, cc2, hours=19)

    p = run_monthly_payroll(
        db_session, org_id=org.id, employee_id=emp.id,
        fiscal_year_id=fy.id, monat=JAN,
    )
    allocs = sorted(p.allocations, key=lambda a: a.cost_center_id)
    assert len(allocs) == 2
    assert all(a.origin == AllocationOrigin.PCM for a in allocs)
    # Hour-proportional split summing to 100 %.
    assert sum(float(a.prozent) for a in allocs) == pytest.approx(100.0, abs=0.01)
    # Betrag shares sum (within rounding) to AG-Brutto.
    assert sum(float(a.betrag_anteil) for a in allocs) == pytest.approx(
        float(p.betrag_ag_brutto), abs=0.02
    )


def test_run_monthly_payroll_rerun_replaces(db_session, org):
    _gross_factor(db_session, org)
    fy = _fy(db_session, org)
    jan_tariff = _split(db_session, org)
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp, tariff_id=jan_tariff.id)
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=39)

    run_monthly_payroll(db_session, org_id=org.id, employee_id=emp.id,
                        fiscal_year_id=fy.id, monat=JAN)
    p2 = run_monthly_payroll(db_session, org_id=org.id, employee_id=emp.id,
                             fiscal_year_id=fy.id, monat=JAN)

    n_payroll = db_session.execute(
        select(func.count()).select_from(MonthlyPayroll).where(
            MonthlyPayroll.employee_id == emp.id, MonthlyPayroll.monat == JAN
        )
    ).scalar_one()
    n_details = db_session.execute(
        select(func.count()).select_from(PayrollDetailLine).where(
            PayrollDetailLine.monthly_payroll_id == p2.id
        )
    ).scalar_one()
    assert n_payroll == 1  # re-run replaced, not duplicated
    assert n_details == 2  # not 4


def test_run_monthly_payroll_skips_manual(db_session, org):
    fy = _fy(db_session, org)
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp)
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=39)
    # Pre-existing manual payroll for the month.
    db_session.add(MonthlyPayroll(
        org_id=org.id, employee_id=emp.id, fiscal_year_id=fy.id, monat=JAN,
        assigned_hours=Decimal("39"), standard_hours=Decimal("39"),
        base_salary=Decimal("4000"), ag_faktor=Decimal("1.2"),
        actual_salary=Decimal("4000"), betrag_an_brutto=Decimal("4000"),
        betrag_ag_brutto=Decimal("4800"), quelle="MANUELL",
    ))
    db_session.commit()
    with pytest.raises(APIError) as ei:
        run_monthly_payroll(db_session, org_id=org.id, employee_id=emp.id,
                            fiscal_year_id=fy.id, monat=JAN)
    assert ei.value.code == "PAYROLL_EXISTS_MANUAL"


def test_run_monthly_payroll_fiscal_year_closed(db_session, org):
    fy = _fy(db_session, org, status=FiscalYearStatus.GESCHLOSSEN)
    emp = _employee(db_session, org)
    contract = _contract(db_session, org, emp)
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=39)
    with pytest.raises(APIError) as ei:
        run_monthly_payroll(db_session, org_id=org.id, employee_id=emp.id,
                            fiscal_year_id=fy.id, monat=JAN)
    assert ei.value.code == "FISCAL_YEAR_CLOSED"


def test_run_monthly_payroll_no_assignments(db_session, org):
    fy = _fy(db_session, org)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp)
    with pytest.raises(APIError) as ei:
        run_monthly_payroll(db_session, org_id=org.id, employee_id=emp.id,
                            fiscal_year_id=fy.id, monat=JAN)
    assert ei.value.code == "NO_HOUR_ASSIGNMENTS"


def test_run_monthly_payroll_no_contract(db_session, org):
    fy = _fy(db_session, org)
    emp = _employee(db_session, org)
    # Contract starts AFTER the payroll month → no active contract.
    contract = _contract(db_session, org, emp, gueltig_ab=date(2026, 6, 1))
    cc = _cc(db_session, org)
    _wsz(db_session, org, emp, contract, cc, hours=39, effective=date(2026, 6, 1))
    with pytest.raises(APIError) as ei:
        run_monthly_payroll(db_session, org_id=org.id, employee_id=emp.id,
                            fiscal_year_id=fy.id, monat=JAN)
    assert ei.value.code == "NO_CONTRACT"
