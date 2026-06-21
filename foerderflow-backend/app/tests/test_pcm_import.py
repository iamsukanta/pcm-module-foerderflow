"""Module PCM Areas J + P — external payroll import (employee CSV + BAB) and the
Fristen leave-task feed."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import CostCenterTyp, FiscalYearStatus, Vertragsart
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import Employee, EmployeeContract, MonthlyPayroll
from app.models.pcm_personnel import WochenstundenZuweisung

BASE = "/api/protected/pcm"


def _fy(db, org):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    db.add(fy)
    db.commit()
    return fy


def _emp(db, org, code, ext):
    e = Employee(org_id=org.id, employee_code=code, vorname="Anna", nachname=code,
                 eintrittsdatum=date(2026, 1, 1), ist_aktiv=True,
                 employee_external_id=ext)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ── J: employee CSV (quarterly) ───────────────────────────────────────────────
def test_import_quarterly_employee_csv(client, db_session, org):
    _fy(db_session, org)
    emp = _emp(db_session, org, "EMP1", "P-100")
    csv_bytes = b"external_id;ag_brutto\nP-100;6000\n"

    prev = client.post(f"{BASE}/payroll-import/preview",
        files={"file": ("q1.csv", csv_bytes, "text/csv")},
        data={"source_type": "CSV_QUARTERLY", "period_from": "2026-01-01"})
    assert prev.status_code == 200, prev.text
    data = prev.json()["data"]
    assert data["matched_count"] == 1
    row = data["rows"][0]
    assert row["matched_employee_id"] == emp.id
    assert len(row["distribution"]) == 3  # quarterly split
    assert row["distribution"][0]["amount"] == 2000.0

    conf = client.post(f"{BASE}/payroll-import/confirm", json={
        "source_type": "CSV_QUARTERLY", "period_from": "2026-01-01",
        "period_to": "2026-03-01", "note": "Q1", "rows": data["rows"]})
    assert conf.status_code == 200, conf.text
    assert conf.json()["data"]["written"] == 3

    payrolls = db_session.query(MonthlyPayroll).filter(
        MonthlyPayroll.employee_id == emp.id).all()
    assert len(payrolls) == 3
    assert all(p.quelle == "IMPORT" for p in payrolls)
    assert float(payrolls[0].betrag_ag_brutto) == 2000.0

    batches = client.get(f"{BASE}/payroll-import/batches").json()["data"]
    assert len(batches) == 1 and batches[0]["source_type"] == "CSV_QUARTERLY"


# ── J: Diamant BAB (cost-centre distribution by hours) ─────────────────────────
def test_import_bab_distributes_by_hours(client, db_session, org):
    _fy(db_session, org)
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db_session.add(cc)
    db_session.commit()
    db_session.refresh(cc)
    for i, hours in enumerate([30, 10]):
        e = _emp(db_session, org, f"E{i}", f"X{i}")
        c = EmployeeContract(org_id=org.id, employee_id=e.id,
                             vertragsart=Vertragsart.FESTANSTELLUNG,
                             assigned_hours=Decimal(str(hours)), base_salary=Decimal("3000"),
                             gueltig_ab=date(2026, 1, 1))
        db_session.add(c)
        db_session.commit()
        db_session.add(WochenstundenZuweisung(
            org_id=org.id, employee_id=e.id, salary_assignment_id=c.id,
            cost_center_id=cc.id, weekly_hours=Decimal(str(hours)),
            effective_date=date(2026, 1, 1)))
        db_session.commit()

    csv_bytes = b"kostenstelle;betrag\nP1;4000\n"
    prev = client.post(f"{BASE}/payroll-import/preview",
        files={"file": ("bab.csv", csv_bytes, "text/csv")},
        data={"source_type": "DIAMANT_BAB", "period_from": "2026-01-01",
              "period_to": "2026-01-01"})
    assert prev.status_code == 200, prev.text
    data = prev.json()["data"]
    assert data["matched_count"] == 2
    shares = sorted(r["gross"] for r in data["rows"])
    assert shares == [1000.0, 3000.0]  # 10h→1000, 30h→3000 of 4000


# ── P: Fristen leave tasks ─────────────────────────────────────────────────────
def test_fristen_leave_tasks(client, db_session, org):
    emp = _emp(db_session, org, "EMP1", "P-1")
    client.post(f"{BASE}/leave-periods", json={
        "employee_id": emp.id, "leave_type": "ELTERNZEIT", "start_date": "2026-06-15",
        "expected_end_date": "2026-06-30", "funder_notification_required": True})
    data = client.get(f"{BASE}/fristen/leave-tasks").json()["data"]
    types = {t["type"] for t in data["tasks"]}
    assert "LEAVE_NOTIFICATION" in types
    assert "RETURN_CHECK" in types  # expected return within 14 days of 2026-06-21
