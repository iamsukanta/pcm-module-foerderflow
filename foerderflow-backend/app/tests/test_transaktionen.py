"""Transaktionen core parity tests (list/cockpit, details, patch)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.master import FiscalYear
from app.models.transaction import Transaction


@pytest.fixture
def seeded(client, db_session, org):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(fy)
    db_session.flush()
    txs = [
        Transaction(
            org_id=org.id, fiscal_year_id=fy.id, datum=date(2026, 3, 1),
            betrag=Decimal("1000.00"), typ="EINNAHME", auftraggeber="Spender A",
            verwendungszweck="Spende", status="IMPORTIERT",
        ),
        Transaction(
            org_id=org.id, fiscal_year_id=fy.id, datum=date(2026, 3, 5),
            betrag=Decimal("-250.50"), typ="AUSGABE", auftraggeber="Vermieter",
            verwendungszweck="Miete März", status="ZUGEORDNET",
        ),
    ]
    db_session.add_all(txs)
    db_session.commit()
    return {"fy": fy.id, "tx_ids": [t.id for t in txs]}


def test_list_basic(client, seeded):
    r = client.get("/api/protected/transaktionen")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pagination"]["total"] == 2
    assert {t["betrag"] for t in body["data"]} == {"1000", "-250.5"}
    assert body["data"][0]["_count"] == {"splits": 0, "belege": 0}
    assert body["data"][0]["confidence"] is None


def test_list_filters(client, seeded):
    r = client.get("/api/protected/transaktionen?status=ZUGEORDNET")
    assert r.json()["pagination"]["total"] == 1
    assert r.json()["data"][0]["auftraggeber"] == "Vermieter"

    r = client.get("/api/protected/transaktionen?search=spende")
    assert r.json()["pagination"]["total"] == 1

    r = client.get("/api/protected/transaktionen?betrag_min=0")
    assert r.json()["pagination"]["total"] == 1
    assert r.json()["data"][0]["betrag"] == "1000"


def test_list_cockpit_kpis(client, seeded):
    r = client.get("/api/protected/transaktionen?cockpit=true")
    body = r.json()
    assert "kpis" in body
    k = body["kpis"]
    assert k["einnahmen"] == 1000.0
    assert k["ausgaben"] == -250.5
    assert k["cashflow"] == 749.5
    assert k["total"] == 2 and k["zugeordnet"] == 1
    assert k["fortschritt"] == 50
    # cockpit rows include splits + massnahme
    assert "massnahme" in body["data"][0]


def test_pagination(client, seeded):
    r = client.get("/api/protected/transaktionen?limit=1&page=1")
    assert r.json()["pagination"] == {"page": 1, "limit": 1, "total": 2, "pages": 2}
    assert len(r.json()["data"]) == 1


def test_get_details(client, seeded):
    tid = seeded["tx_ids"][0]
    r = client.get(f"/api/protected/transaktionen/{tid}")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["id"] == tid
    assert d["splits"] == [] and d["belege"] == []
    assert d["rule_applications"] == []


def test_get_not_found(client, seeded):
    r = client.get("/api/protected/transaktionen/nope")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_patch(client, seeded):
    tid = seeded["tx_ids"][0]
    r = client.patch(f"/api/protected/transaktionen/{tid}", json={"notiz": "geprüft", "auftraggeber": "Spender B"})
    assert r.status_code == 200
    assert r.json()["data"]["notiz"] == "geprüft"
    assert r.json()["data"]["auftraggeber"] == "Spender B"

    # invalid kostenbereich
    r = client.patch(f"/api/protected/transaktionen/{tid}", json={"kostenbereich_id": "bad"})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_KOSTENBEREICH"
