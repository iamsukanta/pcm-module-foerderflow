"""Fördermassnahmen (FundingMeasure) parity tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def funder_id(client) -> str:
    r = client.post("/api/protected/funder", json={"name": "Stiftung X", "typ": "STIFTUNG"})
    assert r.status_code == 201
    return r.json()["data"]["id"]


def _base_payload(funder_id: str) -> dict:
    return {
        "funder_id": funder_id,
        "name": "Projekt Alpha",
        "budget_gesamt": 100000,
        "foerderquote": 80,
        "laufzeit_von": "2026-01-01",
        "laufzeit_bis": "2026-12-31",
        "mittelabruf_verfahren": "ABRUF",
    }


def test_create_and_get(client, funder_id):
    r = client.post("/api/protected/foerdermassnahmen", json=_base_payload(funder_id))
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["budget_gesamt"] == "100000"  # Decimal -> string
    assert data["foerderquote"] == "80"
    assert data["status"] == "AKTIV"
    assert data["funder"]["name"] == "Stiftung X"
    assert data["_count"] == {"rules": 0, "cost_centers": 0}
    assert "days_until_expiry" in data
    mid = data["id"]

    r = client.get(f"/api/protected/foerdermassnahmen/{mid}")
    assert r.status_code == 200
    assert r.json()["data"]["funder"]["typ"] == "STIFTUNG"


def test_validation_codes(client, funder_id):
    p = _base_payload(funder_id)
    p["budget_gesamt"] = -5
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_BUDGET"

    p = _base_payload(funder_id)
    p["foerderquote"] = 150
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_FOERDERQUOTE"

    p = _base_payload(funder_id)
    p["laufzeit_von"], p["laufzeit_bis"] = "2026-12-31", "2026-01-01"
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_LAUFZEIT_RANGE"

    p = _base_payload(funder_id)
    p["mittelabruf_verfahren"] = "FOO"
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_VERFAHREN"

    p = _base_payload(funder_id)
    p["funder_id"] = "does-not-exist"
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 422 and r.json()["code"] == "FUNDER_NOT_FOUND"


def test_durchfuehrung_partial(client, funder_id):
    p = _base_payload(funder_id)
    p["durchfuehrungs_von"] = "2026-02-01"  # bis missing
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_DURCHFUEHRUNG_PARTIAL"

    p = _base_payload(funder_id)
    p["durchfuehrungs_von"] = "2025-01-01"  # outside Bewilligung
    p["durchfuehrungs_bis"] = "2026-06-30"
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_DURCHFUEHRUNG_OUTSIDE_BEWILLIGUNG"


def test_rules_and_cost_centers(client, funder_id):
    cc = client.post(
        "/api/protected/kostenstellen",
        json={"name": "KST1", "code": "K1", "typ": "PROJECT"},
    ).json()["data"]["id"]
    p = _base_payload(funder_id)
    p["rules"] = [{"typ": "EIGENANTEIL_MIN", "schluessel": "20.00", "wert": "20"}]
    p["cost_center_ids"] = [cc]
    r = client.post("/api/protected/foerdermassnahmen", json=p)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["_count"] == {"rules": 1, "cost_centers": 1}
    assert data["cost_centers"][0]["cost_center"]["code"] == "K1"

    # invalid rule type
    p2 = _base_payload(funder_id)
    p2["name"] = "Projekt Beta"
    p2["rules"] = [{"typ": "BOGUS", "schluessel": "x"}]
    r = client.post("/api/protected/foerdermassnahmen", json=p2)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_RULE_TYP"


def test_update_status_lock_and_revoke(client, funder_id):
    mid = client.post(
        "/api/protected/foerdermassnahmen", json=_base_payload(funder_id)
    ).json()["data"]["id"]

    # update name
    r = client.patch(f"/api/protected/foerdermassnahmen/{mid}", json={"name": "Neu"})
    assert r.status_code == 200 and r.json()["data"]["name"] == "Neu"

    # set ABGESCHLOSSEN, then only WIDERRUFEN allowed
    client.patch(f"/api/protected/foerdermassnahmen/{mid}", json={"status": "ABGESCHLOSSEN"})
    r = client.patch(f"/api/protected/foerdermassnahmen/{mid}", json={"name": "X"})
    assert r.status_code == 422 and r.json()["code"] == "STATUS_LOCKED"
    r = client.patch(f"/api/protected/foerdermassnahmen/{mid}", json={"status": "WIDERRUFEN"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "WIDERRUFEN"


def test_rules_subresource(client, funder_id):
    mid = client.post(
        "/api/protected/foerdermassnahmen", json=_base_payload(funder_id)
    ).json()["data"]["id"]

    r = client.post(
        f"/api/protected/foerdermassnahmen/{mid}/regeln",
        json={"typ": "EIGENANTEIL_MIN", "schluessel": "20.00", "wert": "20"},
    )
    assert r.status_code == 201
    rule_id = r.json()["data"]["id"]
    assert r.json()["message"] == "Regel wurde hinzugefügt."

    r = client.get(f"/api/protected/foerdermassnahmen/{mid}/regeln")
    assert len(r.json()["data"]) == 1

    # invalid type
    r = client.post(
        f"/api/protected/foerdermassnahmen/{mid}/regeln",
        json={"typ": "BOGUS", "schluessel": "x"},
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_TYP"

    # delete
    r = client.delete(f"/api/protected/foerdermassnahmen/{mid}/regeln/{rule_id}")
    assert r.status_code == 200 and r.json()["data"] is None
    assert len(client.get(f"/api/protected/foerdermassnahmen/{mid}/regeln").json()["data"]) == 0


def test_cost_center_subresource(client, funder_id):
    mid = client.post(
        "/api/protected/foerdermassnahmen", json=_base_payload(funder_id)
    ).json()["data"]["id"]
    cc = client.post(
        "/api/protected/kostenstellen",
        json={"name": "KST-X", "code": "KX", "typ": "PROJECT"},
    ).json()["data"]["id"]

    r = client.post(
        f"/api/protected/foerdermassnahmen/{mid}/kostenstellen",
        json={"cost_center_id": cc},
    )
    assert r.status_code == 201
    assert r.json()["data"]["cost_center"]["code"] == "KX"

    # duplicate
    r = client.post(
        f"/api/protected/foerdermassnahmen/{mid}/kostenstellen",
        json={"cost_center_id": cc},
    )
    assert r.status_code == 409 and r.json()["code"] == "COST_CENTER_DUPLICATE"

    # remove
    r = client.request(
        "DELETE",
        f"/api/protected/foerdermassnahmen/{mid}/kostenstellen",
        json={"cost_center_id": cc},
    )
    assert r.status_code == 200 and r.json()["data"] is None


def test_subresource_blocked_when_revoked(client, funder_id):
    mid = client.post(
        "/api/protected/foerdermassnahmen", json=_base_payload(funder_id)
    ).json()["data"]["id"]
    client.delete(f"/api/protected/foerdermassnahmen/{mid}")  # -> WIDERRUFEN
    r = client.post(
        f"/api/protected/foerdermassnahmen/{mid}/regeln",
        json={"typ": "EIGENANTEIL_MIN", "schluessel": "20"},
    )
    assert r.status_code == 422 and r.json()["code"] == "MEASURE_REVOKED"


def test_soft_and_hard_delete(client, funder_id):
    mid = client.post(
        "/api/protected/foerdermassnahmen", json=_base_payload(funder_id)
    ).json()["data"]["id"]

    # soft delete -> WIDERRUFEN
    r = client.delete(f"/api/protected/foerdermassnahmen/{mid}")
    assert r.status_code == 200 and r.json()["data"]["status"] == "WIDERRUFEN"
    # again -> already revoked
    r = client.delete(f"/api/protected/foerdermassnahmen/{mid}")
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_REVOKED"

    # hard delete removes it
    r = client.delete(f"/api/protected/foerdermassnahmen/{mid}?hard=true")
    assert r.status_code == 200
    assert "vollständig gelöscht" in r.json()["message"]
    assert client.get(f"/api/protected/foerdermassnahmen/{mid}").status_code == 404
