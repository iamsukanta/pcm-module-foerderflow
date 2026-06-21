"""Module PCM Area I — payroll period lifecycle: overview, results, preflight,
lock (freezes re-run), reopen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import CostCenterTyp, FiscalYearStatus, Vertragsart
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import (
    Employee,
    EmployeeContract,
    EmployerGrossFactor,
    MonthlyPayroll,
)
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryTariff

BASE = "/api/protected/pcm"


def _setup(client, db, org):
    db.add(EmployerGrossFactor(org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
                               faktor=Decimal("1.2000"), gueltig_ab=date(2026, 1, 1)))
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    tariff = SalaryTariff(org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10",
                          level=3, monthly_amount=Decimal("4500"),
                          standard_hours=Decimal("39.00"), is_proposed=False,
                          valid_from=date(2026, 1, 1), valid_to=None,
                          bav_rate_pct=Decimal("4.70"))
    db.add_all([fy, tariff])
    db.commit()
    emp = Employee(org_id=org.id, employee_code="EMP1", vorname="Anna", nachname="B",
                   eintrittsdatum=date(2026, 1, 1), ist_aktiv=True)
    db.add(emp)
    db.commit()
    contract = EmployeeContract(org_id=org.id, employee_id=emp.id,
                                vertragsart=Vertragsart.FESTANSTELLUNG,
                                assigned_hours=Decimal("39"), base_salary=Decimal("4000"),
                                gueltig_ab=date(2026, 1, 1), salary_tariff_id=tariff.id)
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db.add_all([contract, cc])
    db.commit()
    db.add(WochenstundenZuweisung(org_id=org.id, employee_id=emp.id,
                                  salary_assignment_id=contract.id, cost_center_id=cc.id,
                                  weekly_hours=Decimal("39"), effective_date=date(2026, 1, 1)))
    db.commit()
    client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01"})
    return fy, emp


def test_period_overview_and_results(client, db_session, org):
    fy, emp = _setup(client, db_session, org)
    ov = client.get(f"{BASE}/payroll/periods", params={"fiscal_year_id": fy.id}).json()["data"]
    assert len(ov["periods"]) == 12
    jan = next(p for p in ov["periods"] if p["monat"] == "2026-01-01")
    assert jan["status"] == "CALCULATED" and jan["employee_count"] == 1
    feb = next(p for p in ov["periods"] if p["monat"] == "2026-02-01")
    assert feb["status"] == "NOT_STARTED"

    res = client.get(f"{BASE}/payroll/periods/results",
                     params={"fiscal_year_id": fy.id, "monat": "2026-01-01"}).json()["data"]
    assert res["summary"]["employee_count"] == 1
    assert res["rows"][0]["employee_id"] == emp.id
    assert res["locked"] is False


def test_period_preflight(client, db_session, org):
    fy, _ = _setup(client, db_session, org)
    pf = client.get(f"{BASE}/payroll/periods/preflight",
                    params={"fiscal_year_id": fy.id, "monat": "2026-02-01"}).json()["data"]
    assert pf["in_scope_count"] == 1


def test_lock_blocks_rerun_then_reopen(client, db_session, org):
    fy, emp = _setup(client, db_session, org)
    lock = client.post(f"{BASE}/payroll/periods/lock",
                       json={"fiscal_year_id": fy.id, "monat": "2026-01-01"})
    assert lock.status_code == 200 and lock.json()["data"]["status"] == "LOCKED"

    ov = client.get(f"{BASE}/payroll/periods", params={"fiscal_year_id": fy.id}).json()["data"]
    jan = next(p for p in ov["periods"] if p["monat"] == "2026-01-01")
    assert jan["status"] == "LOCKED"

    # Re-run is blocked while locked.
    blocked = client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01"})
    assert blocked.status_code == 423 and blocked.json()["code"] == "PERIOD_LOCKED"

    # Reopen restores the ability to run.
    client.post(f"{BASE}/payroll/periods/reopen",
                json={"fiscal_year_id": fy.id, "monat": "2026-01-01"})
    ok = client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01"})
    assert ok.status_code == 200, ok.text
    # MonthlyPayroll row still present for the month.
    rows = db_session.query(MonthlyPayroll).filter(
        MonthlyPayroll.employee_id == emp.id).all()
    assert len(rows) == 1
