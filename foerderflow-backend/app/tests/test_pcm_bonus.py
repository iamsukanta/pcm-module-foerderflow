"""Module PCM Areas G & H: bonus templates CRUD + eligibility preview,
per-employee bonus payments & salary adjustments, and the payroll engine's
application of all three to detail lines and brutto."""

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


def _scaffold(db, org):
    """Employee on E10 @ 4500 full-time, 39h on a PROJECT cost centre."""
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
                   eintrittsdatum=date(2024, 1, 1), ist_aktiv=True)
    db.add(emp)
    db.commit()
    contract = EmployeeContract(org_id=org.id, employee_id=emp.id,
                                vertragsart=Vertragsart.FESTANSTELLUNG,
                                assigned_hours=Decimal("39"), base_salary=Decimal("4000"),
                                gueltig_ab=date(2026, 1, 1), entgeltgruppe="E10", stufe=3,
                                salary_tariff_id=tariff.id)
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db.add_all([contract, cc])
    db.commit()
    db.add(WochenstundenZuweisung(org_id=org.id, employee_id=emp.id,
                                  salary_assignment_id=contract.id, cost_center_id=cc.id,
                                  weekly_hours=Decimal("39"), effective_date=date(2026, 1, 1)))
    db.commit()
    return fy, emp


def _run(client, db, emp, fy):
    r = client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-03-01"})
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]
    db.expire_all()
    row = db.get(MonthlyPayroll, pid)
    lines = client.get(f"{BASE}/payroll/{pid}/detail-lines").json()["data"]
    by_comp = {line["component"]: float(line["amount"]) for line in lines}
    return row, by_comp


# ── templates (G) ─────────────────────────────────────────────────────────────
def test_template_crud_and_preview(client, db_session, org):
    _scaffold(db_session, org)  # one active E10 employee
    body = {
        "name": "Münchenzulage EG1–EG12", "salary_group_min": "E1",
        "salary_group_max": "E12", "applicable_to": "ALL", "type": "FIXED",
        "amount": 270, "brutto_type": "EMPLOYER", "proration_rule": "FULL",
        "period_from": "2026-01-01",
    }
    r = client.post(f"{BASE}/bonus-templates", json=body)
    assert r.status_code == 201, r.text
    tid = r.json()["data"]["id"]

    listed = client.get(f"{BASE}/bonus-templates").json()["data"]
    assert listed[0]["matched_count"] == 1  # the E10 employee matches E1–E12

    # Out-of-range group excludes the employee.
    prev = client.post(f"{BASE}/bonus-templates/preview", json={
        "salary_group_min": "E11", "salary_group_max": "E15", "applicable_to": "ALL",
    }).json()["data"]
    assert prev["matched"] == 0 and prev["total"] == 1

    assert client.patch(f"{BASE}/bonus-templates/{tid}",
                        json={**body, "amount": 300}).status_code == 200
    assert client.delete(f"{BASE}/bonus-templates/{tid}").status_code == 200


def test_reference_month_requires_months(client, db_session, org):
    r = client.post(f"{BASE}/bonus-templates", json={
        "name": "JSZ", "type": "REFERENCE_MONTH", "amount": 80,
        "brutto_type": "EMPLOYEE", "period_from": "2026-01-01",
    })
    assert r.status_code == 422 and r.json()["code"] == "MISSING_MONTHS"


# ── per-employee records (H) ──────────────────────────────────────────────────
def test_bonus_payment_and_adjustment_crud(client, db_session, org):
    _, emp = _scaffold(db_session, org)
    bp = client.post(f"{BASE}/bonus-payments", json={
        "employee_id": emp.id, "type": "FIXED", "amount": 150,
        "brutto_type": "EMPLOYEE", "period_from": "2026-01-01", "description": "Prämie"})
    assert bp.status_code == 201, bp.text
    pays = client.get(f"{BASE}/bonus-payments", params={"employee_id": emp.id})
    assert len(pays.json()["data"]) == 1
    assert client.delete(f"{BASE}/bonus-payments/{bp.json()['data']['id']}").status_code == 200

    adj = client.post(f"{BASE}/salary-adjustments", json={
        "employee_id": emp.id, "type": "ADDITION", "amount": 50,
        "brutto_type": "NEITHER", "period_from": "2026-01-01", "description": "Jobticket"})
    assert adj.status_code == 201, adj.text
    adjs = client.get(f"{BASE}/salary-adjustments", params={"employee_id": emp.id})
    assert len(adjs.json()["data"]) == 1


# ── engine integration ────────────────────────────────────────────────────────
def test_engine_applies_bonuses_and_adjustments(client, db_session, org):
    fy, emp = _scaffold(db_session, org)
    # FIXED addition (EMPLOYER, 100), PERCENT bonus (EMPLOYER, 2% → 90),
    # template ZULAGE (EMPLOYER, 50, matches E10).
    client.post(f"{BASE}/salary-adjustments", json={
        "employee_id": emp.id, "type": "ADDITION", "amount": 100,
        "brutto_type": "EMPLOYER", "period_from": "2026-01-01", "description": "Zulage"})
    client.post(f"{BASE}/bonus-payments", json={
        "employee_id": emp.id, "type": "PERCENT", "amount": 2,
        "brutto_type": "EMPLOYER", "period_from": "2026-01-01", "description": "LOB 2%"})
    client.post(f"{BASE}/bonus-templates", json={
        "name": "Projektzulage", "type": "FIXED", "amount": 50,
        "brutto_type": "EMPLOYER", "applicable_to": "ALL", "period_from": "2026-01-01"})

    row, by_comp = _run(client, db_session, emp, fy)
    assert by_comp["BASE"] == 4500.0
    assert by_comp["BAV"] == 211.5
    assert by_comp["ADJUST_ADD"] == 100.0
    assert by_comp["BONUS"] == 90.0
    assert by_comp["ZULAGE"] == 50.0
    # AG-Brutto = 5400 (×1.2) + 211.5 + 100 + 90 + 50
    assert float(row.betrag_ag_brutto) == 5851.5
    assert float(row.betrag_an_brutto) == 4500.0


def test_template_precedence_and_fringe_and_deduction(client, db_session, org):
    fy, emp = _scaffold(db_session, org)
    # Manual FIXED bonus suppresses a FIXED template of the same type.
    client.post(f"{BASE}/bonus-payments", json={
        "employee_id": emp.id, "type": "FIXED", "amount": 70,
        "brutto_type": "EMPLOYER", "period_from": "2026-01-01"})
    client.post(f"{BASE}/bonus-templates", json={
        "name": "Suppressed", "type": "FIXED", "amount": 999,
        "brutto_type": "EMPLOYER", "applicable_to": "ALL", "period_from": "2026-01-01"})
    # NEITHER addition → fringe; EMPLOYEE deduction → reduces both brutti.
    client.post(f"{BASE}/salary-adjustments", json={
        "employee_id": emp.id, "type": "ADDITION", "amount": 30,
        "brutto_type": "NEITHER", "period_from": "2026-01-01", "description": "Jobticket"})
    client.post(f"{BASE}/salary-adjustments", json={
        "employee_id": emp.id, "type": "DEDUCTION", "amount": 80,
        "brutto_type": "EMPLOYEE", "period_from": "2026-01-01", "description": "Dienstwagen"})

    row, by_comp = _run(client, db_session, emp, fy)
    assert by_comp["BONUS"] == 70.0          # manual
    assert "ZULAGE" not in by_comp           # template suppressed by precedence
    assert by_comp["FRINGE"] == 30.0
    assert by_comp["ADJUST_DED"] == -80.0
    assert float(row.fringe_benefits_amount) == 30.0
    assert float(row.betrag_an_brutto) == 4420.0   # 4500 − 80
    # AG = 5400 + 211.5 + 70 (bonus) − 80 (deduction)
    assert float(row.betrag_ag_brutto) == 5601.5
