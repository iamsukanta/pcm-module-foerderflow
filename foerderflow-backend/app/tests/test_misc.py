"""fund-allocations summary, position-wahl, opening-balances parity tests."""

from __future__ import annotations

from datetime import date

import pytest

from app.models.master import FiscalYear


@pytest.fixture
def base(client, db_session, org):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(fy)
    db_session.commit()
    db_session.refresh(fy)
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    acc = client.post(
        "/api/protected/bank-accounts",
        json={"code": "GIRO", "bezeichnung": "Girokonto", "typ": "BANK"},
    ).json()["data"]["id"]
    return {"fy": fy.id, "measure": mid, "account": acc}


def test_fund_allocation_summary_empty(client, base):
    r = client.get(f"/api/protected/fund-allocations/summary?funding_measure_id={base['measure']}")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["total_foerderfahig"] == "0.00"
    assert d["anzahl_transaktionen"] == 0


def test_fund_allocation_summary_missing_param(client):
    r = client.get("/api/protected/fund-allocations/summary")
    assert r.status_code == 400 and r.json()["code"] == "MISSING_PARAMS"


def test_position_wahl_empty(client, base):
    r = client.get("/api/protected/allocations/position-wahl-ausstehend")
    assert r.status_code == 200 and r.json()["data"] == []


def test_opening_balance_upsert_and_list(client, base):
    r = client.post(
        "/api/protected/opening-balances",
        json={"bank_account_id": base["account"], "fiscal_year_id": base["fy"], "saldo_eroeffnung": 1500.50},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["saldo_eroeffnung"] == 1500.50
    assert r.json()["data"]["datum"] == "2026-01-01"  # defaults to fy.beginn

    # upsert replaces
    r = client.post(
        "/api/protected/opening-balances",
        json={"bank_account_id": base["account"], "fiscal_year_id": base["fy"], "saldo_eroeffnung": 2000},
    )
    assert r.status_code == 201
    rows = client.get("/api/protected/opening-balances").json()["data"]
    assert len(rows) == 1 and rows[0]["saldo_eroeffnung"] == 2000.0
    assert rows[0]["bank_account"]["code"] == "GIRO"


def test_opening_balance_validation(client, base):
    r = client.post("/api/protected/opening-balances", json={"saldo_eroeffnung": 100})
    assert r.status_code == 422 and r.json()["code"] == "MISSING_FIELDS"
    r = client.post(
        "/api/protected/opening-balances",
        json={"bank_account_id": "bad", "fiscal_year_id": base["fy"], "saldo_eroeffnung": 100},
    )
    assert r.status_code == 404 and r.json()["code"] == "ACCOUNT_NOT_FOUND"


def test_dashboard_cockpit(client, base):
    r = client.get("/api/protected/dashboard/cockpit")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert "onboarding" in d and "kpi" in d
    assert "measures_top" in d and isinstance(d["measures_top"], list)
    assert "offene_transaktionen" in d
    assert "fehlbedarf" in d and isinstance(d["fehlbedarf"], list)
    assert "ytd_label" in d
