"""Module PCM Area K — cost forecast engine: run, dashboard, matrix, detail,
Stufenaufstieg projection, and MISSING warning."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import CostCenterTyp, FiscalYearStatus, Vertragsart
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import Employee, EmployeeContract, EmployerGrossFactor
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryLevel, SalaryTariff

BASE = "/api/protected/pcm"


def _common(db, org):
    db.add(EmployerGrossFactor(org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
                               faktor=Decimal("1.2000"), gueltig_ab=date(2026, 1, 1)))
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    db.add(fy)
    db.commit()
    return fy


def _tariff(db, org, *, level, amount, valid_from=date(2026, 1, 1)):
    t = SalaryTariff(org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10",
                     level=level, monthly_amount=Decimal(str(amount)),
                     standard_hours=Decimal("39.00"), is_proposed=False,
                     valid_from=valid_from, valid_to=None, bav_rate_pct=Decimal("4.70"))
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _emp_contract(db, org, t3, *, stufe=3, next_level_date=None, with_assignment=True):
    emp = Employee(org_id=org.id, employee_code="EMP1", vorname="Anna", nachname="B",
                   eintrittsdatum=date(2024, 1, 1), ist_aktiv=True)
    db.add(emp)
    db.commit()
    contract = EmployeeContract(org_id=org.id, employee_id=emp.id,
                                vertragsart=Vertragsart.FESTANSTELLUNG,
                                assigned_hours=Decimal("39"), base_salary=Decimal("4500"),
                                gueltig_ab=date(2026, 1, 1), entgeltgruppe="E10", stufe=stufe,
                                salary_tariff_id=t3.id, next_level_date=next_level_date)
    db.add(contract)
    db.commit()
    if with_assignment:
        cc = CostCenter(org_id=org.id, code="P1", name="Projekt",
                        typ=CostCenterTyp.PROJECT, ist_aktiv=True)
        db.add(cc)
        db.commit()
        db.refresh(cc)
        db.add(WochenstundenZuweisung(
            org_id=org.id, employee_id=emp.id, salary_assignment_id=contract.id,
            cost_center_id=cc.id, weekly_hours=Decimal("39"), effective_date=date(2026, 1, 1)))
        db.commit()
    return emp


def _levels(db, org, t, *, l3_months=60):
    db.add_all([
        SalaryLevel(org_id=org.id, tariff_id=t.id, salary_group="E10", level_no=3,
                    monthly_amount=Decimal("4500"), months_to_next_level=l3_months),
        SalaryLevel(org_id=org.id, tariff_id=t.id, salary_group="E10", level_no=4,
                    monthly_amount=Decimal("4900"), months_to_next_level=None),
    ])
    db.commit()


def test_forecast_run_and_reads(client, db_session, org):
    fy = _common(db_session, org)
    t3 = _tariff(db_session, org, level=3, amount=4500)
    emp = _emp_contract(db_session, org, t3)

    run = client.post(f"{BASE}/forecast/run", json={"fiscal_year_id": fy.id})
    assert run.status_code == 200, run.text
    assert run.json()["data"]["row_count"] == 12  # one per month

    dash = client.get(f"{BASE}/forecast/dashboard", params={"fiscal_year_id": fy.id}).json()["data"]
    assert dash["has_forecast"] is True
    assert dash["employee_count"] == 1
    assert len(dash["by_month"]) == 12
    assert float(dash["grand_total"]) > 0

    matrix = client.get(f"{BASE}/forecast/matrix", params={"fiscal_year_id": fy.id}).json()["data"]
    assert len(matrix["rows"]) == 1 and len(matrix["months"]) == 12

    detail = client.get(f"{BASE}/forecast/detail",
                        params={"employee_id": emp.id, "monat": "2026-03-01"}).json()["data"]
    assert detail["forecast_level"] == 3
    assert any(c["component"] == "BASE" for c in detail["components"])
    assert float(detail["total_forecast"]) > 0


def test_forecast_stufenaufstieg(client, db_session, org):
    fy = _common(db_session, org)
    t3 = _tariff(db_session, org, level=3, amount=4500)
    _tariff(db_session, org, level=4, amount=4900)  # so level-4 resolves
    emp = _emp_contract(db_session, org, t3, next_level_date=date(2026, 7, 1))
    _levels(db_session, org, t3)

    client.post(f"{BASE}/forecast/run", json={"fiscal_year_id": fy.id})
    june = client.get(f"{BASE}/forecast/detail",
                      params={"employee_id": emp.id, "monat": "2026-06-01"}).json()["data"]
    august = client.get(f"{BASE}/forecast/detail",
                        params={"employee_id": emp.id, "monat": "2026-08-01"}).json()["data"]
    assert june["forecast_level"] == 3
    assert august["forecast_level"] == 4
    assert float(august["forecast_salary"]) == 4900.0


def test_forecast_missing_warning(client, db_session, org):
    fy = _common(db_session, org)
    t3 = _tariff(db_session, org, level=3, amount=4500)
    _emp_contract(db_session, org, t3, with_assignment=False)

    client.post(f"{BASE}/forecast/run", json={"fiscal_year_id": fy.id})
    w = client.get(f"{BASE}/forecast/warnings", params={"fiscal_year_id": fy.id}).json()["data"]
    assert w["total"] == 12
    assert any(g["warning"] == "MISSING" for g in w["groups"])
