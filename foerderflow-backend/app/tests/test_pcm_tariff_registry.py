"""Module PCM Phase-2 Tariff Registry API tests: tariff-code aggregation,
inline overlap check, rows/levels by code, soft-delete + ROW_IN_USE guard,
fiscal-year write-gate, upcoming progressions, and the CSV import wizard —
all under /api/protected/pcm/*."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.models.enums import FiscalYearStatus, Vertragsart
from app.models.master import FiscalYear
from app.models.payroll import Employee, EmployeeContract
from app.models.pcm_tariff import SalaryLevel, SalaryTariff

BASE = "/api/protected/pcm"


def _tariff(db, org, *, code="TVöD-VKA", group="E10", level=3, amount=4500,
            vfrom="2026-01-01", vto="2026-04-30", proposed=False):
    t = SalaryTariff(
        org_id=org.id, tariff_code=code, salary_group=group, level=level,
        monthly_amount=Decimal(str(amount)), standard_hours=Decimal("39.00"),
        is_proposed=proposed, valid_from=date.fromisoformat(vfrom),
        valid_to=date.fromisoformat(vto) if vto else None,
        bav_rate_pct=Decimal("4.70"),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _employee(db, org, code="EMP1"):
    e = Employee(org_id=org.id, employee_code=code, vorname="Anna", nachname="B",
                 eintrittsdatum=date(2026, 1, 1), ist_aktiv=True)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _contract(db, org, emp, *, tariff_id=None, group=None, stufe=None,
              gueltig_ab=date(2026, 1, 1), next_level_date=None):
    c = EmployeeContract(
        org_id=org.id, employee_id=emp.id, vertragsart=Vertragsart.FESTANSTELLUNG,
        assigned_hours=Decimal("39"), base_salary=Decimal("4500"),
        gueltig_ab=gueltig_ab, salary_tariff_id=tariff_id, entgeltgruppe=group,
        stufe=stufe, next_level_date=next_level_date,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _level(db, org, tariff, *, group="E10", level_no=3, amount=4500, months=60):
    lvl = SalaryLevel(org_id=org.id, tariff_id=tariff.id, salary_group=group,
                      level_no=level_no, monthly_amount=Decimal(str(amount)),
                      months_to_next_level=months)
    db.add(lvl)
    db.commit()
    db.refresh(lvl)
    return lvl


# ── D.1 aggregation ───────────────────────────────────────────────────────────
def test_tariff_codes_aggregation(client, db_session, org):
    cur = _tariff(db_session, org, vfrom="2026-01-01", vto=None)
    _tariff(db_session, org, group="E11", level=4, vfrom="2026-01-01", vto=None,
            proposed=True)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, tariff_id=cur.id, group="E10", stufe=3)

    data = client.get(f"{BASE}/tariff-codes").json()["data"]
    assert len(data) == 1
    row = data[0]
    assert row["tariff_code"] == "TVöD-VKA"
    assert row["grade_count"] == 2
    assert row["has_proposed"] is True
    assert row["employee_count"] == 1


# ── D.3 inline overlap check ──────────────────────────────────────────────────
def test_check_overlap_endpoint(client, db_session, org):
    _tariff(db_session, org, vfrom="2026-01-01", vto=None)
    hit = client.get(f"{BASE}/tariff-rows/check-overlap", params={
        "tariff_code": "TVöD-VKA", "salary_group": "E10", "level": 3,
        "valid_from": "2026-06-01", "is_proposed": "false",
    }).json()["data"]
    assert hit["overlap"] is True
    assert hit["conflict"] is not None

    miss = client.get(f"{BASE}/tariff-rows/check-overlap", params={
        "tariff_code": "TVöD-VKA", "salary_group": "E10", "level": 4,
        "valid_from": "2026-06-01", "is_proposed": "false",
    }).json()["data"]
    assert miss["overlap"] is False


# ── D.2 / D.5 rows + levels by code ───────────────────────────────────────────
def test_rows_and_levels_by_code(client, db_session, org):
    t = _tariff(db_session, org, vfrom="2026-01-01", vto=None)
    _level(db_session, org, t)
    rows = client.get(f"{BASE}/tariff-codes/TVöD-VKA/rows").json()["data"]
    assert len(rows) == 1 and rows[0]["salary_group"] == "E10"
    levels = client.get(f"{BASE}/tariff-codes/TVöD-VKA/levels").json()["data"]
    assert len(levels) == 1 and levels[0]["months_to_next_level"] == 60

    # D.6 edit: bump amount + set maximum tier (months_to_next_level = null).
    lid = levels[0]["id"]
    upd = client.patch(f"{BASE}/salary-levels/{lid}",
                       json={"monthly_amount": 4800, "months_to_next_level": None})
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["months_to_next_level"] is None
    assert upd.json()["data"]["monthly_amount"] == "4800"


# ── §4.5 / §6.3 soft-delete + ROW_IN_USE ──────────────────────────────────────
def test_soft_delete_and_row_in_use(client, db_session, org):
    in_use = _tariff(db_session, org, group="E12", vfrom="2026-01-01", vto=None)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, tariff_id=in_use.id, group="E12", stufe=3)
    r = client.delete(f"{BASE}/salary-tariffs/{in_use.id}")
    assert r.status_code == 422 and r.json()["code"] == "ROW_IN_USE"

    free = _tariff(db_session, org, group="E13", vfrom="2026-01-01", vto=None)
    assert client.delete(f"{BASE}/salary-tariffs/{free.id}").status_code == 200
    # Soft-deleted rows disappear from reads...
    listed = client.get(f"{BASE}/salary-tariffs").json()["data"]
    assert all(t["id"] != free.id for t in listed)
    # ...and no longer block a new row in the same window.
    assert client.post(f"{BASE}/salary-tariffs", json={
        "tariff_code": "TVöD-VKA", "salary_group": "E13", "level": 3,
        "monthly_amount": 4700, "standard_hours": 39, "valid_from": "2026-01-01",
    }).status_code == 201


# ── §6.2 fiscal-year write-gate ───────────────────────────────────────────────
def test_fiscal_year_gate_blocks_create(client, db_session, org):
    db_session.add(FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1),
                              ende=date(2026, 12, 31),
                              status=FiscalYearStatus.GESCHLOSSEN))
    db_session.commit()
    r = client.post(f"{BASE}/salary-tariffs", json={
        "tariff_code": "TVöD-VKA", "salary_group": "E10", "level": 3,
        "monthly_amount": 4500, "standard_hours": 39, "valid_from": "2026-03-01",
    })
    assert r.status_code == 423 and r.json()["code"] == "FISCAL_YEAR_CLOSED"


# ── P-T upcoming progressions ─────────────────────────────────────────────────
def test_progressions_upcoming(client, db_session, org):
    today = date.today()
    start = today - relativedelta(months=58)  # 58 of 60 months done → due in 2
    t = _tariff(db_session, org, group="S6", level=3, vfrom="2020-01-01", vto=None)
    _level(db_session, org, t, group="S6", level_no=3, amount=3370, months=60)
    _level(db_session, org, t, group="S6", level_no=4, amount=3540, months=None)
    emp = _employee(db_session, org)
    _contract(db_session, org, emp, tariff_id=t.id, group="S6", stufe=3,
              gueltig_ab=start)
    data = client.get(f"{BASE}/employees/progressions/upcoming",
                      params={"months_ahead": 6}).json()["data"]
    assert len(data) == 1
    row = data[0]
    assert row["current_level"] == 3 and row["next_level"] == 4
    assert row["delta_monthly"] == "170"


# ── I-T import wizard (CSV) ────────────────────────────────────────────────────
def test_tariff_import_preview_and_confirm(client):
    csv_bytes = (
        b"Grade,Tier1,Tier2,Tier3\n"
        b"E5,2500,2600,2700\n"
        b"E6,2800,2900,3000\n"
    )
    prev = client.post(f"{BASE}/tariff-rows/import",
        files={"file": ("tarif.csv", csv_bytes, "text/csv")},
        data={"source": "CSV", "tariff_code": "AVR-Caritas",
              "is_proposed": "false", "valid_from": "2026-01-01"},
    )
    assert prev.status_code == 200, prev.text
    body = prev.json()["data"]
    assert body["row_count"] == 6 and body["valid_rows"] == 6
    import_id = body["import_id"]

    rows = [{k: r[k] for k in ("salary_group", "level", "monthly_amount")}
            for r in body["preview"]]
    conf = client.post(f"{BASE}/tariff-rows/import/{import_id}/confirm", json={
        "tariff_code": "AVR-Caritas", "is_proposed": False,
        "valid_from": "2026-01-01", "standard_hours": 39, "rows": rows,
    })
    assert conf.status_code == 200, conf.text
    assert conf.json()["data"]["written"] == 6
    written = client.get(f"{BASE}/tariff-codes/AVR-Caritas/rows").json()["data"]
    assert len(written) == 6
