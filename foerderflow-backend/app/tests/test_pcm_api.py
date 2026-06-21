"""Module PCM Phase-3 API tests (TestClient): salary-tariff CRUD + overlap +
resolve + levels, wochenstunden CRUD + Doppelförderungs guard, and the payroll
run / detail-lines endpoints — all under /api/protected/pcm/*."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.enums import CostCenterTyp, FiscalYearStatus, Vertragsart
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import Employee, EmployeeContract, EmployerGrossFactor
from app.models.pcm_tariff import SalaryTariff

BASE = "/api/protected/pcm"


# ── builders (direct DB; the client shares this session) ──────────────────────
def _cc(db, org, code="P1"):
    c = CostCenter(org_id=org.id, code=code, name=f"Projekt {code}",
                   typ=CostCenterTyp.PROJECT, ist_aktiv=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _employee(db, org, code="EMP1"):
    e = Employee(org_id=org.id, employee_code=code, vorname="Anna", nachname="B",
                 eintrittsdatum=date(2026, 1, 1), ist_aktiv=True)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _contract(db, org, emp, *, assigned_hours=39, tariff_id=None):
    c = EmployeeContract(
        org_id=org.id, employee_id=emp.id, vertragsart=Vertragsart.FESTANSTELLUNG,
        assigned_hours=Decimal(str(assigned_hours)), base_salary=Decimal("4000"),
        gueltig_ab=date(2026, 1, 1), salary_tariff_id=tariff_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _tariff(db, org, *, amount=4500, vfrom="2026-01-01", vto="2026-04-30"):
    t = SalaryTariff(
        org_id=org.id, tariff_code="TVöD-VKA", salary_group="E10", level=3,
        monthly_amount=Decimal(str(amount)), standard_hours=Decimal("39.00"),
        is_proposed=False, valid_from=date.fromisoformat(vfrom),
        valid_to=date.fromisoformat(vto) if vto else None, bav_rate_pct=Decimal("4.70"),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _fy(db, org, *, status=FiscalYearStatus.OFFEN):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=status)
    db.add(fy)
    db.commit()
    db.refresh(fy)
    return fy


def _gross_factor(db, org):
    db.add(EmployerGrossFactor(org_id=org.id, vertragsart=Vertragsart.FESTANSTELLUNG,
                               faktor=Decimal("1.2000"), gueltig_ab=date(2026, 1, 1)))
    db.commit()


_TARIFF_BODY = {
    "tariff_code": "TVöD-VKA", "salary_group": "E10", "level": 3,
    "monthly_amount": 4500, "standard_hours": 39, "valid_from": "2026-01-01",
    "valid_to": "2026-04-30", "bav_rate_pct": 4.7,
}


# ── salary tariffs ────────────────────────────────────────────────────────────
def test_salary_tariff_crud_and_overlap(client):
    r = client.post(f"{BASE}/salary-tariffs", json=_TARIFF_BODY)
    assert r.status_code == 201, r.text
    tid = r.json()["data"]["id"]
    assert r.json()["data"]["monthly_amount"] == "4500"

    listed = client.get(f"{BASE}/salary-tariffs").json()["data"]
    assert any(t["id"] == tid for t in listed)

    # Overlapping window → 409.
    overlap = {**_TARIFF_BODY, "valid_from": "2026-04-15", "valid_to": None}
    r2 = client.post(f"{BASE}/salary-tariffs", json=overlap)
    assert r2.status_code == 409
    assert r2.json()["code"] == "TARIFF_WINDOW_OVERLAP"

    # Adjacent non-overlapping window → 201.
    nxt = {**_TARIFF_BODY, "monthly_amount": 4650,
           "valid_from": "2026-05-01", "valid_to": None}
    assert client.post(f"{BASE}/salary-tariffs", json=nxt).status_code == 201

    # PATCH + DELETE.
    assert client.patch(f"{BASE}/salary-tariffs/{tid}",
                        json={"monthly_amount": 4550}).status_code == 200
    assert client.delete(f"{BASE}/salary-tariffs/{tid}").status_code == 200


def test_salary_tariff_resolve_endpoint(client, db_session, org):
    _tariff(db_session, org, amount=4500, vfrom="2026-01-01", vto="2026-04-30")
    _tariff(db_session, org, amount=4650, vfrom="2026-05-01", vto=None)
    r = client.get(f"{BASE}/salary-tariffs/resolve",
                   params={"tariff_code": "TVöD-VKA", "salary_group": "E10",
                           "level": 3, "month": "2026-06-01"})
    assert r.status_code == 200
    assert r.json()["data"]["monthly_amount"] == "4650"


def test_salary_tariff_levels(client):
    tid = client.post(f"{BASE}/salary-tariffs", json=_TARIFF_BODY).json()["data"]["id"]
    r = client.post(f"{BASE}/salary-tariffs/{tid}/levels",
                    json={"level_no": 3, "monthly_amount": 4500, "months_to_next_level": 60})
    assert r.status_code == 201, r.text
    levels = client.get(f"{BASE}/salary-tariffs/{tid}/levels").json()["data"]
    assert len(levels) == 1 and levels[0]["level_no"] == 3


# ── wochenstunden ─────────────────────────────────────────────────────────────
def test_wochenstunden_create_and_guard(client, db_session, org):
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, assigned_hours=39)
    cc = _cc(db_session, org)

    r = client.post(f"{BASE}/wochenstunden-zuweisungen", json={
        "employee_id": emp.id, "cost_center_id": cc.id,
        "weekly_hours": 30, "effective_date": "2026-01-01",
    })
    assert r.status_code == 201, r.text

    # 30 + 15 = 45 > 39 contracted → Doppelförderung 409.
    r2 = client.post(f"{BASE}/wochenstunden-zuweisungen", json={
        "employee_id": emp.id, "cost_center_id": cc.id,
        "weekly_hours": 15, "effective_date": "2026-01-01",
    })
    assert r2.status_code == 409
    assert r2.json()["code"] == "DOPPELFOERDERUNG"

    listed = client.get(f"{BASE}/wochenstunden-zuweisungen",
                        params={"employee_id": emp.id}).json()["data"]
    assert len(listed) == 1


# ── payroll engine endpoints ──────────────────────────────────────────────────
def test_payroll_run_and_detail_lines(client, db_session, org):
    _gross_factor(db_session, org)
    fy = _fy(db_session, org)
    tariff = _tariff(db_session, org)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, tariff_id=tariff.id)
    cc = _cc(db_session, org)
    client.post(f"{BASE}/wochenstunden-zuweisungen", json={
        "employee_id": emp.id, "cost_center_id": cc.id,
        "weekly_hours": 39, "effective_date": "2026-01-01",
    })

    r = client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01",
    })
    assert r.status_code == 200, r.text
    payroll = r.json()["data"]
    pid = payroll["id"]

    lines = client.get(f"{BASE}/payroll/{pid}/detail-lines").json()["data"]
    assert {line["component"] for line in lines} == {"BASE", "BAV"}

    # Re-run replaces (no duplicate / error).
    assert client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01",
    }).status_code == 200

    # Month run picks up the employee with an active assignment.
    run = client.post(f"{BASE}/payroll/run-monat",
                      json={"fiscal_year_id": fy.id, "monat": "2026-01-01"})
    assert run.status_code == 200
    assert run.json()["data"]["run_count"] >= 1


def test_payroll_run_fiscal_year_closed(client, db_session, org):
    fy = _fy(db_session, org, status=FiscalYearStatus.GESCHLOSSEN)
    tariff = _tariff(db_session, org)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, tariff_id=tariff.id)
    cc = _cc(db_session, org)
    client.post(f"{BASE}/wochenstunden-zuweisungen", json={
        "employee_id": emp.id, "cost_center_id": cc.id,
        "weekly_hours": 39, "effective_date": "2026-01-01",
    })
    r = client.post(f"{BASE}/payroll/run", json={
        "employee_id": emp.id, "fiscal_year_id": fy.id, "monat": "2026-01-01",
    })
    assert r.status_code == 409
    assert r.json()["code"] == "FISCAL_YEAR_CLOSED"
