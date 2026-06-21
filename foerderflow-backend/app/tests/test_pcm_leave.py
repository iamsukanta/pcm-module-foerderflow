"""Module PCM Area-F tests: leave periods CRUD, placeholder employees, return
recording, funder-notification, and payroll engine ON_LEAVE suppression."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import CostCenterTyp, EmployeeType, FiscalYearStatus, Vertragsart
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import (
    Employee,
    EmployeeContract,
    EmployerGrossFactor,
    MonthlyPayroll,
)
from app.models.pcm_tariff import SalaryTariff

BASE = "/api/protected/pcm"


def _employee(db, org, code="EMP1", etype=EmployeeType.REGULAR):
    e = Employee(org_id=org.id, employee_code=code, vorname="Anna", nachname="B",
                 eintrittsdatum=date(2026, 1, 1), ist_aktiv=True, employee_type=etype)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _fy(db, org):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    db.add(fy)
    db.commit()
    db.refresh(fy)
    return fy


# ── leave CRUD ────────────────────────────────────────────────────────────────
def test_leave_period_create_list_and_type_guard(client, db_session, org):
    emp = _employee(db_session, org)
    r = client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "ELTERNZEIT",
        "start_date": "2026-03-01", "expected_end_date": "2026-12-31",
        "funder_notification_required": True,
    })
    assert r.status_code == 201, r.text
    lp = r.json()["data"]
    assert lp["status"] == "ACTIVE" and lp["leave_type"] == "ELTERNZEIT"

    listed = client.get(f"{BASE}/leave-periods", params={"status": "active"}).json()["data"]
    assert any(x["id"] == lp["id"] for x in listed)

    pending = client.get(f"{BASE}/leave-periods",
                         params={"notification_pending": "true"}).json()["data"]
    assert any(x["id"] == lp["id"] for x in pending)


def test_placeholder_employee_and_replacement(client, db_session, org):
    emp = _employee(db_session, org)
    ph = client.post(f"{BASE}/placeholder-employees",
                     json={"nachname": "Vertretung Anna"})
    assert ph.status_code == 201, ph.text
    ph_id = ph.json()["data"]["id"]
    assert ph.json()["data"]["employee_code"].startswith("VTR-")

    # Replacement must be a placeholder — a REGULAR employee is rejected.
    other = _employee(db_session, org, code="EMP2")
    bad = client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "MUTTERSCHUTZ",
        "start_date": "2026-04-01", "replacement_employee_id": other.id,
    })
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_REPLACEMENT"

    ok = client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "MUTTERSCHUTZ",
        "start_date": "2026-04-01", "replacement_employee_id": ph_id,
    })
    assert ok.status_code == 201, ok.text
    assert ok.json()["data"]["replacement_employee_id"] == ph_id


def test_leave_return_and_notification(client, db_session, org):
    emp = _employee(db_session, org)
    lp = client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "LANGZEITERKRANKUNG",
        "start_date": "2026-02-01", "funder_notification_required": True,
    }).json()["data"]

    sent = client.post(f"{BASE}/leave-periods/{lp['id']}/notification-sent")
    assert sent.status_code == 200
    assert sent.json()["data"]["funder_notification_sent_at"] is not None

    ret = client.post(f"{BASE}/leave-periods/{lp['id']}/return",
                      json={"actual_end_date": "2026-06-30"})
    assert ret.status_code == 200, ret.text
    assert ret.json()["data"]["status"] == "ENDED"
    assert ret.json()["data"]["actual_end_date"] == "2026-06-30"

    # Return before start is rejected.
    lp2 = client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "OTHER", "start_date": "2026-05-01",
    }).json()["data"]
    bad = client.post(f"{BASE}/leave-periods/{lp2['id']}/return",
                      json={"actual_end_date": "2026-04-01"})
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_DATE_RANGE"


# ── payroll engine ON_LEAVE suppression ───────────────────────────────────────
def test_payroll_on_leave_suppression(client, db_session, org):
    db_session.add(EmployerGrossFactor(org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
                                       faktor=Decimal("1.2000"), gueltig_ab=date(2026, 1, 1)))
    fy = _fy(db_session, org)
    tariff = SalaryTariff(org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10",
                          level=3, monthly_amount=Decimal("4500"),
                          standard_hours=Decimal("39.00"), is_proposed=False,
                          valid_from=date(2026, 1, 1), valid_to=None,
                          bav_rate_pct=Decimal("4.70"))
    db_session.add(tariff)
    db_session.commit()
    db_session.refresh(tariff)
    emp = _employee(db_session, org)
    contract = EmployeeContract(org_id=org.id, employee_id=emp.id,
                                vertragsart=Vertragsart.FESTANSTELLUNG,
                                assigned_hours=Decimal("39"), base_salary=Decimal("4000"),
                                gueltig_ab=date(2026, 1, 1), salary_tariff_id=tariff.id)
    db_session.add(contract)
    db_session.commit()
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db_session.add(cc)
    db_session.commit()
    db_session.refresh(cc)
    client.post(f"{BASE}/wochenstunden-zuweisungen", json={
        "employee_id": emp.id, "cost_center_id": cc.id,
        "weekly_hours": 39, "effective_date": "2026-01-01"})

    # Active leave covering January → ON_LEAVE, zero gross.
    client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "ELTERNZEIT", "start_date": "2026-01-01"})

    r = client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01"})
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]
    row = db_session.get(MonthlyPayroll, pid)
    assert row.status.value == "ON_LEAVE"
    assert float(row.betrag_ag_brutto) == 0.0
    assert float(row.actual_salary) == 0.0
    lines = client.get(f"{BASE}/payroll/{pid}/detail-lines").json()["data"]
    assert lines == []
