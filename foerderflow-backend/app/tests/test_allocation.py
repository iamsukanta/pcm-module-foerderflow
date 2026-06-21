"""Verteilungsschlüssel + Umlage-Pool parity tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def cost_centers(client) -> list[str]:
    ids = []
    for i, code in enumerate(["A1", "A2"]):
        ids.append(
            client.post(
                "/api/protected/kostenstellen",
                json={"name": f"KST {code}", "code": code, "typ": "PROJECT"},
            ).json()["data"]["id"]
        )
    return ids


# ── Verteilungsschlüssel ──────────────────────────────────────────────────────
def test_create_key_sum_invariant(client, cost_centers):
    cc1, cc2 = cost_centers
    # not 100 -> 400 INVARIANT_SUM_NOT_100
    r = client.post(
        "/api/protected/verteilungsschluessel",
        json={
            "name": "Schlüssel A",
            "basis": "MANUELL",
            "gueltig_von": "2026-01-01",
            "positions": [
                {"cost_center_id": cc1, "prozent": 50},
                {"cost_center_id": cc2, "prozent": 40},
            ],
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "INVARIANT_SUM_NOT_100"
    assert r.json()["summe_prozent"] == 90.0

    # exactly 100 -> 201
    r = client.post(
        "/api/protected/verteilungsschluessel",
        json={
            "name": "Schlüssel A",
            "basis": "MANUELL",
            "gueltig_von": "2026-01-01",
            "positions": [
                {"cost_center_id": cc1, "prozent": 60},
                {"cost_center_id": cc2, "prozent": 40},
            ],
        },
    )
    assert r.status_code == 201, r.text
    assert "warnings" in r.json()


def test_key_validation(client, cost_centers):
    cc1, cc2 = cost_centers
    base = {
        "name": "K",
        "basis": "MANUELL",
        "gueltig_von": "2026-01-01",
        "positions": [{"cost_center_id": cc1, "prozent": 100}],
    }
    # name too short
    r = client.post("/api/protected/verteilungsschluessel", json={**base, "name": "K"})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_NAME"
    # bad basis
    r = client.post(
        "/api/protected/verteilungsschluessel", json={**base, "name": "Gut", "basis": "X"}
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_BASIS"
    # duplicate cc
    r = client.post(
        "/api/protected/verteilungsschluessel",
        json={
            **base,
            "name": "Gut",
            "positions": [
                {"cost_center_id": cc1, "prozent": 50},
                {"cost_center_id": cc1, "prozent": 50},
            ],
        },
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_POSITIONS_DUPLICATE"


def test_get_list_and_neue_version(client, cost_centers):
    cc1, cc2 = cost_centers
    kid = client.post(
        "/api/protected/verteilungsschluessel",
        json={
            "name": "Versioniert",
            "basis": "MANUELL",
            "gueltig_von": "2026-01-01",
            "positions": [
                {"cost_center_id": cc1, "prozent": 70},
                {"cost_center_id": cc2, "prozent": 30},
            ],
        },
    ).json()["data"]["id"]

    r = client.get(f"/api/protected/verteilungsschluessel/{kid}")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["summe_prozent"] == 100.0 and d["is_valid"] is True
    assert d["positions"][0]["prozent"] == "70"

    # neue version
    r = client.post(
        f"/api/protected/verteilungsschluessel/{kid}/neue-version",
        json={
            "gueltig_von": "2026-07-01",
            "positions": [
                {"cost_center_id": cc1, "prozent": 50},
                {"cost_center_id": cc2, "prozent": 50},
            ],
        },
    )
    assert r.status_code == 201, r.text
    new_key = r.json()["data"]
    assert new_key["parent_key_id"] == kid
    assert new_key["gueltig_von"] == "2026-07-01"

    # old key now inactive with gueltig_bis = 2026-06-30
    old = client.get(f"/api/protected/verteilungsschluessel/{kid}").json()["data"]
    assert old["ist_aktiv"] is False
    assert old["gueltig_bis"] == "2026-06-30"


def test_patch_and_soft_delete(client, cost_centers):
    cc1 = cost_centers[0]
    kid = client.post(
        "/api/protected/verteilungsschluessel",
        json={
            "name": "ZuÄndern",
            "basis": "MANUELL",
            "gueltig_von": "2026-01-01",
            "positions": [{"cost_center_id": cc1, "prozent": 100}],
        },
    ).json()["data"]["id"]

    r = client.patch(
        f"/api/protected/verteilungsschluessel/{kid}", json={"name": "Geändert"}
    )
    assert r.status_code == 200 and r.json()["data"]["name"] == "Geändert"

    r = client.patch(f"/api/protected/verteilungsschluessel/{kid}", json={})
    assert r.status_code == 422 and r.json()["code"] == "NO_CHANGES"

    r = client.delete(f"/api/protected/verteilungsschluessel/{kid}")
    assert r.status_code == 200 and r.json()["data"]["ist_aktiv"] is False
    r = client.delete(f"/api/protected/verteilungsschluessel/{kid}")
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_INACTIVE"


# ── Umlage-Pools ──────────────────────────────────────────────────────────────
def test_umlage_scope_crud(client, cost_centers):
    cc1, cc2 = cost_centers
    r = client.post(
        "/api/protected/umlage-source-scopes",
        json={"name": "Geschäftsstelle", "cost_center_ids": [cc1, cc2]},
    )
    assert r.status_code == 201, r.text
    sid = r.json()["data"]["id"]
    assert len(r.json()["data"]["cost_centers"]) == 2

    # duplicate name
    r = client.post(
        "/api/protected/umlage-source-scopes",
        json={"name": "Geschäftsstelle", "cost_center_ids": [cc1]},
    )
    assert r.status_code == 409 and r.json()["code"] == "DUPLICATE_NAME"

    # empty ccs
    r = client.post(
        "/api/protected/umlage-source-scopes",
        json={"name": "Leer", "cost_center_ids": []},
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_KSTS"

    r = client.get("/api/protected/umlage-source-scopes")
    assert r.json()["data"][0]["cost_center_count"] == 2
    assert r.json()["data"][0]["position_count"] == 0

    r = client.patch(
        f"/api/protected/umlage-source-scopes/{sid}",
        json={"name": "GS 2026", "cost_center_ids": [cc1]},
    )
    assert r.status_code == 200 and r.json()["data"]["name"] == "GS 2026"
    assert len(client.get(f"/api/protected/umlage-source-scopes/{sid}").json()["data"]["cost_centers"]) == 1

    r = client.delete(f"/api/protected/umlage-source-scopes/{sid}")
    assert r.status_code == 200 and r.json()["message"] == "Pool wurde gelöscht."
