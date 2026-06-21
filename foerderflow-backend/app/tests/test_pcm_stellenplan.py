"""Module PCM Area E.1 — Stellenplan org-wide allocation matrix."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import CostCenterTyp, Vertragsart
from app.models.master import CostCenter
from app.models.payroll import Employee, EmployeeContract

BASE = "/api/protected/pcm"


def test_stellenplan_matrix(client, db_session, org):
    emp = Employee(org_id=org.id, employee_code="EMP1", vorname="Anna", nachname="B",
                   eintrittsdatum=date(2026, 1, 1), ist_aktiv=True)
    db_session.add(emp)
    db_session.commit()
    db_session.add(EmployeeContract(
        org_id=org.id, employee_id=emp.id, vertragsart=Vertragsart.FESTANSTELLUNG,
        assigned_hours=Decimal("39"), base_salary=Decimal("4000"),
        gueltig_ab=date(2026, 1, 1)))
    cc = CostCenter(org_id=org.id, code="P1", name="Projekt", typ=CostCenterTyp.PROJECT,
                    ist_aktiv=True)
    db_session.add(cc)
    db_session.commit()
    db_session.refresh(cc)
    client.post(f"{BASE}/wochenstunden-zuweisungen", json={
        "employee_id": emp.id, "cost_center_id": cc.id,
        "weekly_hours": 30, "effective_date": "2026-01-01"})

    m = client.get(f"{BASE}/stellenplan/matrix", params={"as_of": "2026-06-01"}).json()["data"]
    assert len(m["cost_centers"]) == 1 and m["cost_centers"][0]["code"] == "P1"
    row = next(r for r in m["rows"] if r["employee_id"] == emp.id)
    assert row["capacity"] == 39.0
    assert row["total_allocated"] == 30.0
    assert row["status"] == "UNDER"  # 30h of 39h contracted
    assert row["cells"][cc.id] == 30.0
