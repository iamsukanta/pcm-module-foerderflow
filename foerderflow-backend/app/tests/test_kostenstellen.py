"""Kostenstellen CRUD parity tests."""

from __future__ import annotations


def test_create_list_get(client):
    r = client.post(
        "/api/protected/kostenstellen",
        json={"name": "Projekt A", "code": "PROJ-A", "typ": "PROJECT"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["data"]["code"] == "PROJ-A"
    assert body["data"]["typ"] == "PROJECT"
    assert body["data"]["_count"]["funding_measure_cost_centers"] == 0
    assert "wurde erfolgreich angelegt" in body["message"]
    cc_id = body["data"]["id"]

    r = client.get("/api/protected/kostenstellen")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1

    r = client.get(f"/api/protected/kostenstellen/{cc_id}")
    assert r.status_code == 200
    assert r.json()["data"]["id"] == cc_id
    assert r.json()["data"]["funding_measure_cost_centers"] == []


def test_code_normalized_and_validation(client):
    # lowercase code -> VALIDATION_CODE (monolith validates before uppercasing)
    r = client.post(
        "/api/protected/kostenstellen",
        json={"name": "X", "code": "ab", "typ": "PROJECT"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_NAME"  # name too short fails first

    r = client.post(
        "/api/protected/kostenstellen",
        json={"name": "Gültig", "code": "ab", "typ": "PROJECT"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_CODE"

    r = client.post(
        "/api/protected/kostenstellen",
        json={"name": "Gültig", "code": "OK1", "typ": "FOO"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_TYP"


def test_duplicate_code_conflict(client):
    payload = {"name": "Erste", "code": "DUP", "typ": "OVERHEAD"}
    assert client.post("/api/protected/kostenstellen", json=payload).status_code == 201
    payload["name"] = "Zweite"
    r = client.post("/api/protected/kostenstellen", json=payload)
    assert r.status_code == 409
    assert r.json()["code"] == "CODE_DUPLICATE"


def test_hierarchy_one_level(client):
    parent = client.post(
        "/api/protected/kostenstellen",
        json={"name": "Eltern", "code": "P1", "typ": "PROJECT"},
    ).json()["data"]
    child = client.post(
        "/api/protected/kostenstellen",
        json={"name": "Kind", "code": "C1", "typ": "PROJECT", "parent_id": parent["id"]},
    )
    assert child.status_code == 201
    child_id = child.json()["data"]["id"]
    # grandchild not allowed
    r = client.post(
        "/api/protected/kostenstellen",
        json={"name": "Enkel", "code": "G1", "typ": "PROJECT", "parent_id": child_id},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "HIERARCHY_TOO_DEEP"


def test_soft_delete_cascades_children(client):
    parent = client.post(
        "/api/protected/kostenstellen",
        json={"name": "Eltern", "code": "P2", "typ": "PROJECT"},
    ).json()["data"]
    client.post(
        "/api/protected/kostenstellen",
        json={"name": "Kind", "code": "C2", "typ": "PROJECT", "parent_id": parent["id"]},
    )
    r = client.delete(f"/api/protected/kostenstellen/{parent['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["ist_aktiv"] is False
    assert "warnings" in body and "ebenfalls deaktiviert" in body["warnings"][0]

    # second delete -> already inactive
    r = client.delete(f"/api/protected/kostenstellen/{parent['id']}")
    assert r.status_code == 409
    assert r.json()["code"] == "ALREADY_INACTIVE"

    # default list excludes inactive
    assert len(client.get("/api/protected/kostenstellen").json()["data"]) == 0
    assert (
        len(
            client.get(
                "/api/protected/kostenstellen?includeInactive=true"
            ).json()["data"]
        )
        == 2
    )


def test_not_found(client):
    r = client.get("/api/protected/kostenstellen/nonexistent")
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"
