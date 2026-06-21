"""Payroll import / lohnbüro-export / vzae-übersicht parity tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def fy(db_session, org):
    from app.models.master import FiscalYear

    f = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(f)
    db_session.commit()
    return f.id


@pytest.fixture
def employee(db_session, org):
    from app.models.payroll import Employee, EmployeeContract

    e = Employee(org_id=org.id, employee_code="P-001", vorname="Anna", nachname="Müller", eintrittsdatum=date(2026, 1, 1))
    db_session.add(e)
    db_session.commit()
    c = EmployeeContract(
        org_id=org.id, employee_id=e.id, vertragsart="FESTANSTELLUNG",
        assigned_hours=Decimal("39.00"), base_salary=Decimal("4000.00"),
        entgeltgruppe="E10", stufe=3, gueltig_ab=date(2026, 1, 1),
    )
    db_session.add(c)
    db_session.commit()
    return e.id


def test_import_basic(client, fy, employee):
    csv = "Mitarbeiter;Monat;Bruttoentgelt;AG-Gesamtkosten\r\nP-001;03.2026;4.000,00;4.848,40\r\n"
    r = client.post(
        "/api/protected/payroll/import",
        data={"fiscal_year_id": fy},
        files={"file": ("lohn.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["importiert"] == 1
    assert d["uebersprungen"] == 0
    assert d["nicht_gefunden"] == []


def test_import_duplicate_skipped(client, fy, employee):
    csv = "Mitarbeiter;Monat;Bruttoentgelt;AG-Gesamtkosten\r\nP-001;03.2026;4.000,00;4.848,40\r\n"
    files = {"file": ("lohn.csv", csv.encode("utf-8"), "text/csv")}
    client.post("/api/protected/payroll/import", data={"fiscal_year_id": fy}, files=files)
    r = client.post(
        "/api/protected/payroll/import",
        data={"fiscal_year_id": fy},
        files={"file": ("lohn.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.json()["data"]["uebersprungen"] == 1
    assert r.json()["data"]["importiert"] == 0


def test_import_unknown_employee(client, fy, employee):
    csv = "Mitarbeiter;Monat;Bruttoentgelt;AG-Gesamtkosten\r\nZZZ;03.2026;100,00;120,00\r\n"
    r = client.post(
        "/api/protected/payroll/import",
        data={"fiscal_year_id": fy},
        files={"file": ("lohn.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.json()["data"]["nicht_gefunden"] == ["ZZZ"]


def test_import_missing_fields(client, employee):
    csv = "Mitarbeiter;Monat\r\nP-001;03.2026\r\n"
    r = client.post(
        "/api/protected/payroll/import",
        files={"file": ("lohn.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 400 and r.json()["code"] == "MISSING_FIELDS"


def test_import_fy_not_found(client, employee):
    csv = "Mitarbeiter;Monat;Bruttoentgelt;AG-Gesamtkosten\r\nP-001;03.2026;1,00;1,00\r\n"
    r = client.post(
        "/api/protected/payroll/import",
        data={"fiscal_year_id": "nope"},
        files={"file": ("lohn.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_import_invalid_mapping(client, fy, employee):
    csv = "a;b\r\n1;2\r\n"
    r = client.post(
        "/api/protected/payroll/import",
        data={"fiscal_year_id": fy, "spalten_mapping": "{not json"},
        files={"file": ("lohn.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 400 and r.json()["code"] == "INVALID_MAPPING"


def _make_payroll(db_session, org, fy, employee, cc_codes):
    from app.models.master import CostCenter
    from app.models.payroll import MonthlyPayroll, PayrollAllocation

    p = MonthlyPayroll(
        org_id=org.id, employee_id=employee, fiscal_year_id=fy, monat=date(2026, 3, 1),
        assigned_hours=Decimal("39.00"), standard_hours=Decimal("39.00"),
        base_salary=Decimal("4000.00"), ag_faktor=Decimal("1.2121"),
        actual_salary=Decimal("4000.00"), betrag_an_brutto=Decimal("4000.00"),
        betrag_ag_brutto=Decimal("4848.40"),
    )
    db_session.add(p)
    db_session.commit()
    ccs = []
    for code in cc_codes:
        cc = CostCenter(org_id=org.id, name=f"KST {code}", code=code, typ="PROJECT")
        db_session.add(cc)
        ccs.append(cc)
    db_session.commit()
    for cc in ccs:
        db_session.add(
            PayrollAllocation(
                org_id=org.id, payroll_id=p.id, cost_center_id=cc.id,
                prozent=Decimal("50"), betrag_anteil=Decimal("2424.20"),
            )
        )
    db_session.commit()
    return p.id, [cc.id for cc in ccs]


def test_lohnbuero_export(client, db_session, org, fy, employee):
    _make_payroll(db_session, org, fy, employee, ["K-001", "K-002"])
    r = client.get("/api/protected/payroll/lohnbuero-export", params={"monat": "2026-03"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="lohnschluessel_2026-03.csv"' in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    lines = text.split("\r\n")
    assert lines[0] == "Personalnummer;Name;Kostenstelle;Anteil %;AN-Brutto-Anteil;AG-Brutto-Anteil"
    # one row per KST
    assert "Müller, Anna" in text
    assert "K-001 KST K-001" in text
    assert "2424,20" in text  # ag anteil, German format
    assert "2000,00" in text  # an anteil = 4000 * 50%


def test_lohnbuero_export_bad_monat(client):
    r = client.get("/api/protected/payroll/lohnbuero-export", params={"monat": "2026"})
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_MONAT"


def test_lohnbuero_export_no_columns(client):
    r = client.get(
        "/api/protected/payroll/lohnbuero-export",
        params={"monat": "2026-03", "spalten": "garbage"},
    )
    assert r.status_code == 400 and r.json()["code"] == "NO_COLUMNS"


def test_vzae_uebersicht(client, db_session, org, fy, employee):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    _pid, cc_ids = _make_payroll(db_session, org, fy, employee, ["K-001"])

    from app.models.funding import FundingMeasureCostCenter

    db_session.add(
        FundingMeasureCostCenter(org_id=org.id, funding_measure_id=mid, cost_center_id=cc_ids[0])
    )
    db_session.commit()

    r = client.get(
        "/api/protected/personal/vzae-uebersicht",
        params={"funding_measure_id": mid, "fiscal_year_id": fy},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["massnahme"]["name"] == "Maßnahme"
    assert d["massnahme"]["laufzeit_von"] == "2026-01-01T00:00:00.000Z"
    assert len(d["monate"]) == 1
    m = d["monate"][0]
    assert m["monat"] == "2026-03"
    # 50% of 1.0 VZÄ
    assert m["summe_vzae_projekt"] == pytest.approx(0.5)
    assert m["summe_betrag"] == pytest.approx(2424.20)
    assert d["gesamt_betrag"] == pytest.approx(2424.20)


def test_vzae_uebersicht_missing_params(client):
    r = client.get("/api/protected/personal/vzae-uebersicht", params={"funding_measure_id": "x"})
    assert r.status_code == 400 and r.json()["code"] == "MISSING_PARAMS"


def test_vzae_uebersicht_measure_not_found(client, fy):
    r = client.get(
        "/api/protected/personal/vzae-uebersicht",
        params={"funding_measure_id": "nope", "fiscal_year_id": fy},
    )
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_vzae_uebersicht_no_kst(client, fy):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    r = client.get(
        "/api/protected/personal/vzae-uebersicht",
        params={"funding_measure_id": mid, "fiscal_year_id": fy},
    )
    assert r.status_code == 200
    assert r.json()["monate"] == []
    assert r.json()["gesamt_betrag"] == 0
