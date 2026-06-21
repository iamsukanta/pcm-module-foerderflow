"""Module PCM Area L — scenario planner: CRUD, compute (hour/level/growth/hire
overrides), results, and promote (re-runs the committed forecast)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import CostCenterTyp, FiscalYearStatus, Vertragsart
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import Employee, EmployeeContract, EmployerGrossFactor
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryTariff

BASE = "/api/protected/pcm"


def _scaffold(db, org):
    db.add(EmployerGrossFactor(org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
                               faktor=Decimal("1.2000"), gueltig_ab=date(2026, 1, 1)))
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    t = SalaryTariff(org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10", level=3,
                     monthly_amount=Decimal("4500"), standard_hours=Decimal("39.00"),
                     is_proposed=False, valid_from=date(2026, 1, 1), valid_to=None,
                     bav_rate_pct=Decimal("4.70"))
    db.add_all([fy, t])
    db.commit()
    emp = Employee(org_id=org.id, employee_code="EMP1", vorname="Anna", nachname="B",
                   eintrittsdatum=date(2024, 1, 1), ist_aktiv=True)
    db.add(emp)
    db.commit()
    contract = EmployeeContract(org_id=org.id, employee_id=emp.id,
                                vertragsart=Vertragsart.FESTANSTELLUNG,
                                assigned_hours=Decimal("39"), base_salary=Decimal("4500"),
                                gueltig_ab=date(2026, 1, 1), entgeltgruppe="E10", stufe=3,
                                salary_tariff_id=t.id)
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db.add_all([contract, cc])
    db.commit()
    db.refresh(cc)
    db.add(WochenstundenZuweisung(org_id=org.id, employee_id=emp.id,
                                  salary_assignment_id=contract.id, cost_center_id=cc.id,
                                  weekly_hours=Decimal("39"), effective_date=date(2026, 1, 1)))
    db.commit()
    return fy, emp


def _create(client, fy, **params):
    r = client.post(f"{BASE}/scenarios", json={
        "name": "Test", "fiscal_year_id": fy.id, "params": params})
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def test_scenario_hours_override_reduces_cost(client, db_session, org):
    fy, emp = _scaffold(db_session, org)
    sid = _create(client, fy, hour_overrides=[{"employee_id": emp.id, "weekly_hours": 20}])
    res = client.post(f"{BASE}/scenarios/{sid}/compute").json()["data"]
    assert res["scenario"]["status"] == "COMPUTED"
    assert float(res["scenario"]["delta_total"]) < 0  # 20h < 39h → cheaper
    assert len(res["by_month"]) == 12

    listed = client.get(f"{BASE}/scenarios").json()["data"]
    assert any(s["id"] == sid for s in listed)


def test_scenario_growth_rate_increases_cost(client, db_session, org):
    fy, _ = _scaffold(db_session, org)
    sid = _create(client, fy, growth_rate_pct=10)
    res = client.post(f"{BASE}/scenarios/{sid}/compute").json()["data"]
    assert float(res["scenario"]["delta_total"]) > 0
    assert float(res["scenario"]["scenario_total"]) > float(res["scenario"]["baseline_total"])


def test_scenario_hire_adds_cost(client, db_session, org):
    fy, _ = _scaffold(db_session, org)
    sid = _create(client, fy, hires=[{
        "name": "Neue Stelle E10/3", "tariff_code": "TVöD-VKA", "salary_group": "E10",
        "level": 3, "weekly_hours": 39, "start_month": "2026-07-01"}])
    res = client.post(f"{BASE}/scenarios/{sid}/compute").json()["data"]
    # Hire is pure addition (baseline 0) for Jul–Dec.
    assert float(res["scenario"]["delta_total"]) > 0
    hire_row = next(e for e in res["by_employee"] if e["employee_id"] is None)
    assert float(hire_row["baseline"]) == 0.0 and float(hire_row["scenario"]) > 0


def test_scenario_promote_updates_forecast(client, db_session, org):
    fy, emp = _scaffold(db_session, org)
    sid = _create(client, fy, hour_overrides=[{"employee_id": emp.id, "weekly_hours": 20}])
    client.post(f"{BASE}/scenarios/{sid}/compute")
    pr = client.post(f"{BASE}/scenarios/{sid}/promote")
    assert pr.status_code == 200, pr.text
    assert pr.json()["data"]["status"] == "PROMOTED"

    detail = client.get(f"{BASE}/forecast/detail",
                        params={"employee_id": emp.id, "monat": "2026-03-01"}).json()["data"]
    assert float(detail["forecast_hours"]) == 20.0  # override committed
