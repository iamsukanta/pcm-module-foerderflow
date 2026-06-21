"""Finanzplan-Positionen parity tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def measure_id(client) -> str:
    fid = client.post(
        "/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}
    ).json()["data"]["id"]
    return client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid,
            "name": "Maßnahme",
            "budget_gesamt": 50000,
            "foerderquote": 100,
            "laufzeit_von": "2026-01-01",
            "laufzeit_bis": "2026-12-31",
            "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]


def test_create_list_get(client, measure_id):
    r = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": measure_id,
            "positionscode": "1.1",
            "bezeichnung": "Personalkosten",
            "betrag_bewilligt": 30000,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["betrag_bewilligt"] == 30000  # number, not string
    assert data["ueberziehung_limit_pct"] == 20  # default
    pid = data["id"]

    r = client.get(f"/api/protected/finanzplan-positionen?funding_measure_id={measure_id}")
    assert r.status_code == 200 and len(r.json()["data"]) == 1
    assert r.json()["data"][0]["_count"]["fund_allocations"] == 0

    r = client.get(f"/api/protected/finanzplan-positionen/{pid}")
    assert r.status_code == 200
    assert r.json()["data"]["funding_measure"]["name"] == "Maßnahme"


def test_list_requires_measure_param(client):
    r = client.get("/api/protected/finanzplan-positionen")
    assert r.status_code == 400 and r.json()["code"] == "MISSING_PARAM"


def test_validation(client, measure_id):
    base = {
        "funding_measure_id": measure_id,
        "positionscode": "1",
        "bezeichnung": "X",
        "betrag_bewilligt": 100,
    }
    r = client.post("/api/protected/finanzplan-positionen", json={**base, "betrag_bewilligt": -1})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_BETRAG"

    r = client.post("/api/protected/finanzplan-positionen", json={**base, "positionscode": ""})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_CODE"


def test_pauschale_typ_required(client, measure_id):
    r = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": measure_id,
            "positionscode": "VW",
            "bezeichnung": "Verwaltung",
            "betrag_bewilligt": 1000,
            "ist_pauschale": True,
        },
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_PAUSCHALE_TYP"


def test_pauschale_fixer_betrag_ok(client, measure_id):
    r = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": measure_id,
            "positionscode": "VW",
            "bezeichnung": "Verwaltung",
            "betrag_bewilligt": 1000,
            "ist_pauschale": True,
            "pauschale_typ": "FIXER_BETRAG",
        },
    )
    assert r.status_code == 201
    assert r.json()["data"]["pauschale_typ"] == "FIXER_BETRAG"


def test_prozent_gesamt_recursion_guard(client, measure_id):
    payload = {
        "funding_measure_id": measure_id,
        "positionscode": "P1",
        "bezeichnung": "Pausch1",
        "betrag_bewilligt": 100,
        "ist_pauschale": True,
        "pauschale_typ": "PROZENT_GESAMT",
        "pauschale_prozent": 10,
    }
    assert client.post("/api/protected/finanzplan-positionen", json=payload).status_code == 201
    payload["positionscode"] = "P2"
    payload["bezeichnung"] = "Pausch2"
    r = client.post("/api/protected/finanzplan-positionen", json=payload)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_PAUSCHALE_REKURSION"


def test_umlage_requires_all_fks(client, measure_id):
    r = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": measure_id,
            "positionscode": "U1",
            "bezeichnung": "Umlage",
            "betrag_bewilligt": 100,
            "ist_pauschale": True,
            "pauschale_typ": "UMLAGE_KOSTENSTELLEN",
        },
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_UMLAGE_FKS"


def test_update_and_delete(client, measure_id):
    pid = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": measure_id,
            "positionscode": "1.1",
            "bezeichnung": "Alt",
            "betrag_bewilligt": 100,
        },
    ).json()["data"]["id"]

    r = client.patch(
        f"/api/protected/finanzplan-positionen/{pid}",
        json={"bezeichnung": "Neu", "betrag_bewilligt": 200},
    )
    assert r.status_code == 200
    assert r.json()["data"]["bezeichnung"] == "Neu"
    assert r.json()["data"]["betrag_bewilligt"] == 200

    r = client.delete(f"/api/protected/finanzplan-positionen/{pid}")
    assert r.status_code == 200 and r.json()["message"] == "Position wurde gelöscht."


def test_deckungsfaehigkeit(client, measure_id):
    # no pool
    pid = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": measure_id,
            "positionscode": "A",
            "bezeichnung": "A",
            "betrag_bewilligt": 1000,
        },
    ).json()["data"]["id"]
    r = client.get(f"/api/protected/finanzplan-positionen/{pid}/deckungsfaehigkeit")
    assert r.status_code == 200
    assert r.json()["data"]["pool"] is None
    assert r.json()["data"]["deckungsfaehig"] is None

    # with pool
    p2 = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": measure_id,
            "positionscode": "B",
            "bezeichnung": "B",
            "betrag_bewilligt": 1000,
            "deckungsfaehigkeit_pool": "POOL1",
            "ueberziehung_limit_pct": 20,
        },
    ).json()["data"]["id"]
    r = client.get(f"/api/protected/finanzplan-positionen/{p2}/deckungsfaehigkeit")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["pool"] == "POOL1"
    assert d["pool_gesamt_bewilligt"] == 1200.0  # 1000 * 1.2
    assert d["pool_gesamt_ist"] == 0
    assert d["deckungsfaehig"] is True
