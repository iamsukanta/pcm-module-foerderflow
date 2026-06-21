"""Parity tests for Funder, Kostenbereiche, Haushaltsjahre, Bank-Accounts."""

from __future__ import annotations


# ── Funder ───────────────────────────────────────────────────────────────────
def test_funder_crud_and_type_restriction(client):
    r = client.post("/api/protected/funder", json={"name": "Stiftung X", "typ": "STIFTUNG"})
    assert r.status_code == 201
    fid = r.json()["data"]["id"]
    assert r.json()["data"]["_count"]["funding_measures"] == 0

    # KIRCHE exists in the DB enum but is NOT accepted by this endpoint (parity)
    r = client.post("/api/protected/funder", json={"name": "Kirche Y", "typ": "KIRCHE"})
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_TYP"

    r = client.get("/api/protected/funder")
    assert len(r.json()["data"]) == 1

    r = client.patch(f"/api/protected/funder/{fid}", json={"name": "Stiftung Z"})
    assert r.status_code == 200
    assert "aktualisiert" in r.json()["message"]

    r = client.delete(f"/api/protected/funder/{fid}")
    assert r.status_code == 200
    assert r.json()["data"] is None


# ── Haushaltsjahre ───────────────────────────────────────────────────────────
def test_haushaltsjahr_create_validation_and_close(client):
    r = client.post(
        "/api/protected/haushaltsjahre",
        json={"jahr": 2026, "beginn": "2026-01-01", "ende": "2026-12-31"},
    )
    assert r.status_code == 201, r.text
    fy = r.json()["data"]
    assert fy["beginn"] == "2026-01-01" and fy["status"] == "OFFEN"

    # duplicate year
    r = client.post(
        "/api/protected/haushaltsjahre",
        json={"jahr": 2026, "beginn": "2026-01-01", "ende": "2026-12-31"},
    )
    assert r.status_code == 409 and r.json()["code"] == "JAHR_DUPLICATE"

    # date order
    r = client.post(
        "/api/protected/haushaltsjahre",
        json={"jahr": 2027, "beginn": "2027-12-31", "ende": "2027-01-01"},
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_DATES_ORDER"

    # second year warns about the still-open one
    r = client.post(
        "/api/protected/haushaltsjahre",
        json={"jahr": 2027, "beginn": "2027-01-01", "ende": "2027-12-31"},
    )
    assert r.status_code == 201 and "warning" in r.json()

    # close requires confirmation
    r = client.post(f"/api/protected/haushaltsjahre/{fy['id']}/close", json={})
    assert r.status_code == 400 and r.json()["code"] == "CONFIRMATION_REQUIRED"

    r = client.post(
        f"/api/protected/haushaltsjahre/{fy['id']}/close",
        json={"confirmation": "SCHLIESSEN"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "GESCHLOSSEN"

    # closed year cannot be edited
    r = client.patch(
        f"/api/protected/haushaltsjahre/{fy['id']}", json={"beginn": "2026-02-01"}
    )
    assert r.status_code == 403 and r.json()["code"] == "FISCAL_YEAR_CLOSED"

    # closing again -> already closed
    r = client.post(
        f"/api/protected/haushaltsjahre/{fy['id']}/close",
        json={"confirmation": "SCHLIESSEN"},
    )
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_CLOSED"


# ── Bank accounts ────────────────────────────────────────────────────────────
def test_bank_account_crud_and_iban(client):
    r = client.post(
        "/api/protected/bank-accounts",
        json={"code": "GIRO", "bezeichnung": "Girokonto", "typ": "BANK",
              "iban": "DE89 3704 0044 0532 0130 00"},
    )
    assert r.status_code == 201, r.text
    acc = r.json()["data"]
    assert acc["iban"] == "DE89370400440532013000"  # whitespace stripped

    # invalid IBAN
    r = client.post(
        "/api/protected/bank-accounts",
        json={"code": "K2", "bezeichnung": "Kasse", "typ": "KASSE", "iban": "XX!"},
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_IBAN"

    # duplicate code
    r = client.post(
        "/api/protected/bank-accounts",
        json={"code": "GIRO", "bezeichnung": "Andere", "typ": "BANK"},
    )
    assert r.status_code == 409 and r.json()["code"] == "CODE_DUPLICATE"

    # list with saldo fields
    r = client.get("/api/protected/bank-accounts")
    rows = r.json()["data"]
    assert rows[0]["saldo_aktuell"] == 0 and rows[0]["_count"]["transactions"] == 0

    # delete (no dependents)
    r = client.delete(f"/api/protected/bank-accounts/{acc['id']}")
    assert r.status_code == 200 and r.json()["message"] == "Konto gelöscht."


# ── Kostenbereiche (read-only) ───────────────────────────────────────────────
def test_kostenbereiche_list_empty(client):
    r = client.get("/api/protected/kostenbereiche")
    assert r.status_code == 200
    assert r.json() == {"data": []}
