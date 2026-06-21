"""Belege (receipt) parity tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.master import FiscalYear
from app.models.transaction import Transaction


@pytest.fixture
def tx_id(client, db_session, org):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(fy)
    db_session.flush()
    t = Transaction(
        org_id=org.id, fiscal_year_id=fy.id, datum=date(2026, 3, 1),
        betrag=Decimal("-100.00"), typ="AUSGABE", status="IMPORTIERT",
    )
    db_session.add(t)
    db_session.commit()
    return t.id


def test_external_reference(client, tx_id):
    r = client.post(
        f"/api/protected/transaktionen/{tx_id}/belege",
        data={"externe_referenz": "DATEV-2026-042", "retention_years": "10"},
    )
    assert r.status_code == 201, r.text
    b = r.json()["data"]
    assert b["externe_referenz"] == "DATEV-2026-042"
    assert "datei_pfad" not in b  # security: never returned
    assert b["retention_until"].startswith(str(date.today().year + 10))


def test_upload_file(client, tx_id):
    r = client.post(
        f"/api/protected/transaktionen/{tx_id}/belege",
        files={"file": ("rechnung.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert r.status_code == 201, r.text
    bid = r.json()["data"]["id"]
    assert r.json()["data"]["datei_name"] == "rechnung.pdf"

    # download streams the file
    r = client.get(f"/api/protected/transaktionen/{tx_id}/belege/{bid}")
    assert r.status_code == 200
    assert r.content == b"%PDF-1.4 test"


def test_upload_rejects_bad_type(client, tx_id):
    r = client.post(
        f"/api/protected/transaktionen/{tx_id}/belege",
        files={"file": ("virus.exe", b"MZ", "application/x-msdownload")},
    )
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_requires_file_or_ref(client, tx_id):
    r = client.post(f"/api/protected/transaktionen/{tx_id}/belege", data={})
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_list_and_soft_delete(client, tx_id):
    client.post(
        f"/api/protected/transaktionen/{tx_id}/belege",
        data={"externe_referenz": "REF-1"},
    )
    bid = client.get(f"/api/protected/transaktionen/{tx_id}/belege").json()["data"][0]["id"]

    r = client.delete(f"/api/protected/transaktionen/{tx_id}/belege/{bid}")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Beleg wurde als gelöscht markiert"
    assert "warning" in r.json()  # retention still running

    # gone from active list
    assert client.get(f"/api/protected/transaktionen/{tx_id}/belege").json()["data"] == []
    # second delete -> 404
    r = client.delete(f"/api/protected/transaktionen/{tx_id}/belege/{bid}")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_belege_tx_not_found(client):
    r = client.get("/api/protected/transaktionen/nope/belege")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"
