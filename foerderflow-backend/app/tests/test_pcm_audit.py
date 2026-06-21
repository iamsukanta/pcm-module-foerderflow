"""Module PCM Area O + Promotion Job: audit logging of contract changes and
leave events, the automatic Stufenaufstieg job, and the audit-log read API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import Vertragsart
from app.models.payroll import Employee, EmployeeContract
from app.models.pcm_tariff import SalaryLevel, SalaryTariff

BASE = "/api/protected/pcm"


def _log(client, action):
    return client.get(f"{BASE}/audit-log", params={"action_type": action}).json()["data"]


def _employee(db, org, code="EMP1"):
    e = Employee(org_id=org.id, employee_code=code, vorname="Anna", nachname="B",
                 eintrittsdatum=date(2024, 1, 1), ist_aktiv=True)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _tariff_with_levels(db, org):
    t = SalaryTariff(org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10", level=3,
                     monthly_amount=Decimal("4500"), standard_hours=Decimal("39.00"),
                     is_proposed=False, valid_from=date(2020, 1, 1), valid_to=None,
                     bav_rate_pct=Decimal("4.70"))
    db.add(t)
    db.commit()
    db.refresh(t)
    db.add_all([
        SalaryLevel(org_id=org.id, tariff_id=t.id, salary_group="E10", level_no=3,
                    monthly_amount=Decimal("4500"), months_to_next_level=60),
        SalaryLevel(org_id=org.id, tariff_id=t.id, salary_group="E10", level_no=4,
                    monthly_amount=Decimal("4900"), months_to_next_level=None),
    ])
    db.commit()
    return t


def _contract(db, org, emp, tariff, *, stufe=3, next_level_date=None,
              gueltig_ab=date(2026, 1, 1)):
    c = EmployeeContract(org_id=org.id, employee_id=emp.id,
                         vertragsart=Vertragsart.FESTANSTELLUNG,
                         assigned_hours=Decimal("39"), base_salary=Decimal("4500"),
                         gueltig_ab=gueltig_ab, entgeltgruppe="E10", stufe=stufe,
                         salary_tariff_id=tariff.id, next_level_date=next_level_date)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ── contract change audit ─────────────────────────────────────────────────────
def test_contract_change_writes_audit_log(client, db_session, org):
    t = _tariff_with_levels(db_session, org)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, t, gueltig_ab=date(2026, 1, 1))
    r = client.post(f"/api/protected/employees/{emp.id}/contracts", json={
        "vertragsart": "FESTANSTELLUNG", "assigned_hours": 39, "base_salary": 4700,
        "gueltig_ab": "2026-07-01", "entgeltgruppe": "E10", "stufe": 3})
    assert r.status_code == 201, r.text
    log = _log(client, "UPDATE")
    assert any(e["action_type"] == "UPDATE" for e in log)


# ── leave audit ───────────────────────────────────────────────────────────────
def test_leave_writes_audit_logs(client, db_session, org):
    emp = _employee(db_session, org)
    lp = client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "ELTERNZEIT",
        "start_date": "2026-03-01"}).json()["data"]
    starts = _log(client, "LEAVE_START")
    assert len(starts) == 1 and starts[0]["leave_period_id"] == lp["id"]

    client.post(f"{BASE}/leave-periods/{lp['id']}/return", json={"actual_end_date": "2026-08-01"})
    ends = _log(client, "LEAVE_END")
    assert len(ends) == 1
    detail = client.get(f"{BASE}/audit-log/{ends[0]['id']}").json()["data"]
    assert detail["new_values"]["actual_end_date"] == "2026-08-01"


# ── promotion job ─────────────────────────────────────────────────────────────
def test_promotion_job_promotes_and_logs(client, db_session, org):
    t = _tariff_with_levels(db_session, org)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, t, stufe=3, next_level_date=date(2026, 3, 1))

    r = client.post(f"{BASE}/employees/promotions/run")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["promoted_count"] == 1
    assert data["promoted"][0]["to_level"] == 4
    assert data["promoted"][0]["new_amount"] == "4900"

    contracts = (
        db_session.query(EmployeeContract)
        .filter(EmployeeContract.employee_id == emp.id)
        .order_by(EmployeeContract.gueltig_ab)
        .all()
    )
    assert len(contracts) == 2
    assert contracts[0].gueltig_bis == date(2026, 2, 28)
    assert contracts[1].stufe == 4 and float(contracts[1].base_salary) == 4900.0
    assert contracts[1].gueltig_ab == date(2026, 3, 1)

    promos = _log(client, "AUTO_PROMOTION")
    assert len(promos) == 1


def test_promotion_job_skips_on_leave(client, db_session, org):
    t = _tariff_with_levels(db_session, org)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, t, stufe=3, next_level_date=date(2026, 3, 1))
    client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "ELTERNZEIT", "start_date": "2026-02-01"})

    data = client.post(f"{BASE}/employees/promotions/run").json()["data"]
    assert data["promoted_count"] == 0
    assert data["skipped"][0]["code"] == "ON_LEAVE"
