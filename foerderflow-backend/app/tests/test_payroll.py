"""Payroll module parity tests (employees, contracts, components, payroll,
allocations, gross-factors, tarif, soll-ist)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.payroll import EmployerGrossFactor, TarifTabelle
from app.services.personal.berechnung import berechne_gehalt


@pytest.fixture
def base(client, db_session, org):
    # gross factor for FESTANSTELLUNG so payroll uses it (else default 1.2121)
    db_session.add(
        EmployerGrossFactor(
            org_id=org.id, vertragsart="FESTANSTELLUNG", faktor=Decimal("1.2000"),
            gueltig_ab=date(2026, 1, 1),
        )
    )
    db_session.commit()
    hjid = client.post(
        "/api/protected/haushaltsjahre",
        json={"jahr": 2026, "beginn": "2026-01-01", "ende": "2026-12-31"},
    ).json()["data"]["id"]
    cc = client.post(
        "/api/protected/kostenstellen", json={"name": "Projekt", "code": "P1", "typ": "PROJECT"}
    ).json()["data"]["id"]
    return {"hj": hjid, "cc": cc}


def _create_employee(client):
    return client.post(
        "/api/protected/employees",
        json={
            "employee_code": "EMP1", "vorname": "Anna", "nachname": "Beispiel",
            "eintrittsdatum": "2026-01-01",
            "erster_vertrag": {
                "vertragsart": "FESTANSTELLUNG", "assigned_hours": 39, "base_salary": 3900,
                "gueltig_ab": "2026-01-01",
            },
        },
    )


# ── pure calc ───────────────────────────────────────────────────────────────
def test_berechne_gehalt():
    r = berechne_gehalt(
        base_salary=4000, assigned_hours=20, standard_hours=40, ag_faktor=1.2,
        components=[{"betrag": 100, "nach_multiplikator": False}, {"betrag": 50, "nach_multiplikator": True}],
    )
    assert r.actual_salary == 2000
    assert r.an_brutto == 2100  # 2000 + 100
    assert r.ag_brutto == 2100 * 1.2 + 50


# ── employees / contracts / components ────────────────────────────────────────
def test_employee_crud(client, base):
    r = _create_employee(client)
    assert r.status_code == 201, r.text
    emp = r.json()["data"]
    assert emp["employee_code"] == "EMP1"
    assert len(emp["contracts"]) == 1
    assert emp["contracts"][0]["base_salary"] == "3900"
    eid = emp["id"]

    # duplicate code
    r = _create_employee(client)
    assert r.status_code == 422 and r.json()["code"] == "CODE_DUPLICATE"

    # list + get
    assert len(client.get("/api/protected/employees").json()["data"]) == 1
    assert client.get(f"/api/protected/employees/{eid}").json()["data"]["vorname"] == "Anna"

    # update
    r = client.patch(f"/api/protected/employees/{eid}", json={"vorname": "Anja"})
    assert r.status_code == 200 and r.json()["data"]["vorname"] == "Anja"


def test_contract_versioning(client, base):
    eid = _create_employee(client).json()["data"]["id"]
    # new contract closes the prior one
    r = client.post(
        f"/api/protected/employees/{eid}/contracts",
        json={"vertragsart": "FESTANSTELLUNG", "assigned_hours": 30, "base_salary": 3000, "gueltig_ab": "2026-07-01"},
    )
    assert r.status_code == 201, r.text
    contracts = client.get(f"/api/protected/employees/{eid}/contracts").json()["data"]
    assert len(contracts) == 2
    old = next(c for c in contracts if c["assigned_hours"] == "39")
    assert old["gueltig_bis"].startswith("2026-06-30")

    # gueltig_ab not after latest -> error
    r = client.post(
        f"/api/protected/employees/{eid}/contracts",
        json={"vertragsart": "FESTANSTELLUNG", "assigned_hours": 20, "base_salary": 2000, "gueltig_ab": "2026-05-01"},
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_GUELTIG_AB_ORDER"


def test_salary_components(client, base):
    eid = _create_employee(client).json()["data"]["id"]
    cid = client.get(f"/api/protected/employees/{eid}/contracts").json()["data"][0]["id"]
    r = client.post(
        f"/api/protected/employees/{eid}/contracts/{cid}/components",
        json={"typ": "JOBTICKET_SACHBEZUG", "bezeichnung": "Jobticket", "betrag": 49, "nach_multiplikator": True},
    )
    assert r.status_code == 201
    comp_id = r.json()["data"]["id"]
    assert len(client.get(f"/api/protected/employees/{eid}/contracts/{cid}/components").json()["data"]) == 1
    # deactivate
    r = client.patch(
        f"/api/protected/employees/{eid}/contracts/{cid}/components?action=deactivate&componentId={comp_id}"
    )
    assert r.status_code == 200
    assert len(client.get(f"/api/protected/employees/{eid}/contracts/{cid}/components").json()["data"]) == 0


# ── payroll ───────────────────────────────────────────────────────────────────
def test_payroll_create_and_calc(client, base):
    eid = _create_employee(client).json()["data"]["id"]
    r = client.post(
        "/api/protected/payroll",
        json={"employee_id": eid, "fiscal_year_id": base["hj"], "monat": "2026-03"},
    )
    assert r.status_code == 201, r.text
    p = r.json()["data"]
    # 3900 * 39/39 = 3900 actual; an_brutto 3900; ag_brutto 3900*1.2 = 4680
    assert p["actual_salary"] == "3900"
    assert p["betrag_an_brutto"] == "3900"
    assert p["betrag_ag_brutto"] == "4680"
    assert p["monat"] == "2026-03-01"

    # duplicate month
    r = client.post(
        "/api/protected/payroll",
        json={"employee_id": eid, "fiscal_year_id": base["hj"], "monat": "2026-03"},
    )
    assert r.status_code == 409 and r.json()["code"] == "DUPLICATE"


def test_payroll_no_contract(client, base):
    eid = _create_employee(client).json()["data"]["id"]
    r = client.post(
        "/api/protected/payroll",
        json={"employee_id": eid, "fiscal_year_id": base["hj"], "monat": "2025-03"},
    )
    assert r.status_code == 422 and r.json()["code"] == "NO_CONTRACT"


def test_payroll_allocations(client, base):
    eid = _create_employee(client).json()["data"]["id"]
    pid = client.post(
        "/api/protected/payroll",
        json={"employee_id": eid, "fiscal_year_id": base["hj"], "monat": "2026-03"},
    ).json()["data"]["id"]

    # not summing 100 -> 400
    r = client.post(
        f"/api/protected/payroll/{pid}/allocations",
        json={"allocations": [{"cost_center_id": base["cc"], "prozent": 50}]},
    )
    assert r.status_code == 400 and r.json()["code"] == "INVARIANT_SUM_NOT_100"

    # 100% -> betrag_anteil = full ag_brutto 4680
    r = client.post(
        f"/api/protected/payroll/{pid}/allocations",
        json={"allocations": [{"cost_center_id": base["cc"], "prozent": 100}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["betrag_anteil"] == "4680"

    # delete blocked while allocations exist
    r = client.delete(f"/api/protected/payroll/{pid}")
    assert r.status_code == 422 and r.json()["code"] == "HAS_ALLOCATIONS"


def test_monat_uebersicht(client, base):
    eid = _create_employee(client).json()["data"]["id"]
    client.post(
        "/api/protected/payroll",
        json={"employee_id": eid, "fiscal_year_id": base["hj"], "monat": "2026-03"},
    )
    r = client.get("/api/protected/payroll/monat-uebersicht?monat=2026-03")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) == 1 and rows[0]["hat_abrechnung"] is True


# ── gross factors + tarif ──────────────────────────────────────────────────────
def test_gross_factors(client, base):
    r = client.post(
        "/api/protected/employer-gross-factors",
        json={"vertragsart": "MINIJOB", "faktor": 1.3, "gueltig_ab": "2026-01-01"},
    )
    assert r.status_code == 201
    assert r.json()["data"]["faktor"] == "1.3"
    r = client.get("/api/protected/employer-gross-factors")
    assert any(f["vertragsart"] == "MINIJOB" for f in r.json()["data"])


def test_tarif_lookup(client, db_session):
    db_session.add(TarifTabelle(tarifwerk="TVOEDD", entgeltgruppe="E9a", stufe=1, jahr=2026, betrag=Decimal("3500.00")))
    db_session.add(TarifTabelle(tarifwerk="TVOEDD", entgeltgruppe="E9a", stufe=2, jahr=2026, betrag=Decimal("3700.00")))
    db_session.commit()
    r = client.get("/api/protected/tarif?tarifwerk=TVOEDD&entgeltgruppe=E9a&jahr=2026")
    assert r.status_code == 200
    assert r.json()["data"] == [{"stufe": 1, "betrag": "3500.00"}, {"stufe": 2, "betrag": "3700.00"}]
    # invalid tarifwerk
    r = client.get("/api/protected/tarif?tarifwerk=BOGUS&entgeltgruppe=E9a&jahr=2026")
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_TARIFWERK"


def test_personal_soll_ist(client, base):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 50000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
            "cost_center_ids": [base["cc"]],
        },
    ).json()["data"]["id"]
    r = client.get(f"/api/protected/personal/soll-ist?funding_measure_id={mid}")
    assert r.status_code == 200
    assert "gesamt_soll" in r.json() and "gesamt_ist" in r.json()
