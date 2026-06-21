"""Module PCM Areas N & M — payroll allocation views + VWN itemized report."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import (
    CostCenterTyp,
    FiscalYearStatus,
    FunderTyp,
    MittelabrufVerfahren,
    Vertragsart,
)
from app.models.finanzplan import FinanzplanPosition
from app.models.funding import FundingMeasure
from app.models.master import CostCenter, FiscalYear, Funder
from app.models.payroll import Employee, EmployeeContract, EmployerGrossFactor
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryTariff

BASE = "/api/protected/pcm"


def _scaffold(client, db, org):
    db.add(EmployerGrossFactor(org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
                               faktor=Decimal("1.2000"), gueltig_ab=date(2026, 1, 1)))
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    tariff = SalaryTariff(org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10",
                          level=3, monthly_amount=Decimal("4500"),
                          standard_hours=Decimal("39.00"), is_proposed=False,
                          valid_from=date(2026, 1, 1), valid_to=None,
                          bav_rate_pct=Decimal("4.70"))
    funder = Funder(org_id=org.id, name="Stadt", typ=FunderTyp.KOMMUNE)
    db.add_all([fy, tariff, funder])
    db.commit()
    fm = FundingMeasure(org_id=org.id, funder_id=funder.id, name="Hausaufgabenhilfe",
                        budget_gesamt=Decimal("100000"), foerderquote=Decimal("80"),
                        laufzeit_von=date(2026, 1, 1), laufzeit_bis=date(2026, 12, 31),
                        mittelabruf_verfahren=MittelabrufVerfahren.ANFORDERUNG)
    db.add(fm)
    db.commit()
    fp = FinanzplanPosition(org_id=org.id, funding_measure_id=fm.id, positionscode="1.1",
                            bezeichnung="Personalkosten", betrag_bewilligt=Decimal("50000"))
    emp = Employee(org_id=org.id, employee_code="EMP1", vorname="Anna", nachname="B",
                   eintrittsdatum=date(2026, 1, 1), ist_aktiv=True)
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db.add_all([fp, emp, cc])
    db.commit()
    contract = EmployeeContract(org_id=org.id, employee_id=emp.id,
                                vertragsart=Vertragsart.FESTANSTELLUNG,
                                assigned_hours=Decimal("39"), base_salary=Decimal("4000"),
                                gueltig_ab=date(2026, 1, 1), salary_tariff_id=tariff.id)
    db.add(contract)
    db.commit()
    db.add(WochenstundenZuweisung(org_id=org.id, employee_id=emp.id,
                                  salary_assignment_id=contract.id, cost_center_id=cc.id,
                                  funding_measure_id=fm.id, finanzplan_position_id=fp.id,
                                  weekly_hours=Decimal("39"), effective_date=date(2026, 1, 1)))
    db.commit()
    client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01"})
    return fy, fm, emp


def test_allocation_overview_and_per_grant(client, db_session, org):
    fy, fm, emp = _scaffold(client, db_session, org)
    ov = client.get(f"{BASE}/allocations/overview",
                    params={"fiscal_year_id": fy.id, "monat": "2026-01-01"}).json()["data"]
    assert len(ov["groups"]) == 1
    g = ov["groups"][0]
    assert g["funding_measure_id"] == fm.id
    assert float(g["total"]) > 0 and float(ov["grand_total"]) > 0

    pg = client.get(f"{BASE}/allocations/per-grant",
                    params={"fiscal_year_id": fy.id, "funding_measure_id": fm.id}).json()["data"]
    assert len(pg["rows"]) == 1 and len(pg["months"]) == 1
    assert pg["rows"][0]["employee_id"] == emp.id


def test_vwn_config_preview_and_export(client, db_session, org):
    _, fm, _ = _scaffold(client, db_session, org)
    cfg = client.get(f"{BASE}/vwn/config", params={"funding_measure_id": fm.id}).json()["data"]
    assert "BASE" in cfg["visible_components"]

    prev = client.get(f"{BASE}/vwn/preview", params={
        "funding_measure_id": fm.id, "from_month": "2026-01-01", "to_month": "2026-12-01",
    }).json()["data"]
    assert "BASE" in prev["components"]
    assert len(prev["rows"]) == 1
    assert float(prev["grand_total"]) > 0

    # Restrict visible components → others roll into the aggregate column.
    save = client.put(f"{BASE}/vwn/config", json={
        "funding_measure_id": fm.id, "visible_components": ["BASE"], "hide_zero": True})
    assert save.status_code == 200
    prev2 = client.get(f"{BASE}/vwn/preview", params={
        "funding_measure_id": fm.id, "from_month": "2026-01-01", "to_month": "2026-12-01",
    }).json()["data"]
    assert prev2["components"] == ["BASE"]
    assert prev2["has_aggregate"] is True  # BAV rolled into Sonstiges

    exp = client.get(f"{BASE}/vwn/export", params={
        "funding_measure_id": fm.id, "from_month": "2026-01-01", "to_month": "2026-12-01"})
    assert exp.status_code == 200
    assert "text/csv" in exp.headers["content-type"]
    assert "Mitarbeiter" in exp.text
