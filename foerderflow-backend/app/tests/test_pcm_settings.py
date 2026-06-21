"""Module PCM Area A — settings: setup overview, org BAV rate (+ engine
fallback), external-system ID mapping."""

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
from app.models.pcm_tariff import SalaryTariff

BASE = "/api/protected/pcm"


def _employee(db, org, code="EMP1"):
    e = Employee(org_id=org.id, employee_code=code, vorname="Anna", nachname="B",
                 eintrittsdatum=date(2026, 1, 1), ist_aktiv=True)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def test_settings_overview_and_bav(client, db_session, org):
    ov = client.get(f"{BASE}/settings/overview").json()["data"]
    assert ov["checklist"]["has_employees"] is False
    assert ov["checklist"]["bav_configured"] is False

    # Invalid rate rejected.
    bad = client.put(f"{BASE}/settings/bav", json={"bav_rate_pct": 150})
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_RATE"

    ok = client.put(f"{BASE}/settings/bav", json={"bav_rate_pct": 4.7})
    assert ok.status_code == 200
    assert ok.json()["data"]["bav_rate_pct"] == "4.7"

    ov2 = client.get(f"{BASE}/settings/overview").json()["data"]
    assert ov2["checklist"]["bav_configured"] is True
    assert ov2["bav_rate_pct"] == "4.7"


def test_external_id_mapping(client, db_session, org):
    emp = _employee(db_session, org)
    listed = client.get(f"{BASE}/settings/external-ids").json()["data"]
    assert any(e["id"] == emp.id and e["employee_external_id"] is None for e in listed)

    upd = client.put(f"{BASE}/settings/external-ids/{emp.id}",
                     json={"employee_external_id": "P-4711"})
    assert upd.status_code == 200
    assert upd.json()["data"]["employee_external_id"] == "P-4711"


def test_org_bav_fallback_applies(client, db_session, org):
    # Tariff WITHOUT its own BAV rate → the org default is used.
    db_session.add(EmployerGrossFactor(org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
                                       faktor=Decimal("1.2000"), gueltig_ab=date(2026, 1, 1)))
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    tariff = SalaryTariff(org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10",
                          level=3, monthly_amount=Decimal("4500"),
                          standard_hours=Decimal("39.00"), is_proposed=False,
                          valid_from=date(2026, 1, 1), valid_to=None, bav_rate_pct=None)
    db_session.add_all([fy, tariff])
    db_session.commit()
    emp = _employee(db_session, org)
    contract = EmployeeContract(org_id=org.id, employee_id=emp.id,
                                vertragsart=Vertragsart.FESTANSTELLUNG,
                                assigned_hours=Decimal("39"), base_salary=Decimal("4000"),
                                gueltig_ab=date(2026, 1, 1), salary_tariff_id=tariff.id)
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db_session.add_all([contract, cc])
    db_session.commit()
    db_session.refresh(cc)
    client.post(f"{BASE}/wochenstunden-zuweisungen", json={
        "employee_id": emp.id, "cost_center_id": cc.id,
        "weekly_hours": 39, "effective_date": "2026-01-01"})

    client.put(f"{BASE}/settings/bav", json={"bav_rate_pct": 5})
    r = client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01"})
    assert r.status_code == 200, r.text
    row = db_session.get(MonthlyPayroll, r.json()["data"]["id"])
    assert float(row.bav_amount) == 225.0  # 5% of 4500 actual salary
