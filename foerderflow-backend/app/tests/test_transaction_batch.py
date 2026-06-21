"""massnahme + confirm + batch ops parity tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.booking_rule import BookingRule, BookingRuleApplication
from app.models.master import FiscalYear
from app.models.transaction import Transaction


@pytest.fixture
def setup(client, db_session, org):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(fy)
    db_session.flush()
    txs = []
    for i in range(2):
        t = Transaction(
            org_id=org.id, fiscal_year_id=fy.id, datum=date(2026, 3, 1 + i),
            betrag=Decimal("-500.00"), typ="AUSGABE", status="IMPORTIERT",
        )
        db_session.add(t)
        txs.append(t)
    db_session.commit()
    cc = client.post(
        "/api/protected/kostenstellen", json={"name": "Projekt", "code": "P1", "typ": "PROJECT"}
    ).json()["data"]["id"]
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 50,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    return {"tx_ids": [t.id for t in txs], "cc": cc, "measure": mid, "fy": fy.id}


def _add_splits(client, tid, cc):
    client.put(
        f"/api/protected/transaktionen/{tid}/splits",
        json={"splits": [{"cost_center_id": cc, "prozent": 100}]},
    )


def test_massnahme_assign(client, setup):
    tid = setup["tx_ids"][0]
    _add_splits(client, tid, setup["cc"])
    r = client.post(
        f"/api/protected/transaktionen/{tid}/massnahme",
        json={"funding_measure_id": setup["measure"]},
    )
    assert r.status_code == 200 and r.json()["message"] == "Fördermassnahme zugeordnet."
    d = client.get(f"/api/protected/transaktionen/{tid}").json()["data"]
    assert d["status"] == "ZUGEORDNET"
    # one allocation per split, 50% quote on 500 -> förderung 250
    assert d["splits"][0]["fund_allocations"][0]["funding_measure"]["id"] == setup["measure"]


def test_massnahme_requires_splits(client, setup):
    tid = setup["tx_ids"][0]
    r = client.post(
        f"/api/protected/transaktionen/{tid}/massnahme",
        json={"funding_measure_id": setup["measure"]},
    )
    assert r.status_code == 404
    assert "Keine KST-Splits" in r.json()["error"]


def test_confirm_raises_rule_confidence(client, db_session, setup):
    tid = setup["tx_ids"][0]
    # seed a booking rule + application (ORANGE, count 1)
    rule = BookingRule(org_id=setup_org_id(setup, db_session), name="R", match_count=1, confidence="ORANGE")
    db_session.add(rule)
    db_session.flush()
    db_session.add(
        BookingRuleApplication(
            org_id=rule.org_id, transaction_id=tid, rule_id=rule.id, confidence="ORANGE"
        )
    )
    db_session.commit()

    r = client.patch(f"/api/protected/transaktionen/{tid}/confirm")
    assert r.status_code == 200 and r.json()["message"] == "Transaktion bestätigt."
    db_session.refresh(rule)
    assert rule.match_count == 2 and rule.confidence == "GELB"
    assert client.get(f"/api/protected/transaktionen/{tid}").json()["data"]["status"] == "KATEGORISIERT"


def setup_org_id(setup, db_session):
    return db_session.get(Transaction, setup["tx_ids"][0]).org_id


def test_batch_confirm(client, setup):
    r = client.post(
        "/api/protected/transaktionen/batch-confirm",
        json={"transaction_ids": setup["tx_ids"]},
    )
    assert r.status_code == 200
    assert r.json()["data"]["confirmed"] == 2
    assert "2 Transaktion(en) bestätigt" in r.json()["message"]


def test_batch_massnahme_with_filter(client, setup):
    for tid in setup["tx_ids"]:
        _add_splits(client, tid, setup["cc"])
    r = client.post(
        "/api/protected/transaktionen/batch-massnahme",
        json={"funding_measure_id": setup["measure"], "filter": {"status": "KATEGORISIERT"}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["matched"] == 2


def test_batch_input_validation(client, setup):
    r = client.post("/api/protected/transaktionen/batch-confirm", json={})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_INPUT"

    r = client.post(
        "/api/protected/transaktionen/batch-massnahme",
        json={"funding_measure_id": setup["measure"], "filter": {"status": "ABGESCHLOSSEN"}},
    )
    assert r.status_code == 422 and r.json()["code"] == "FILTER_EMPTY"
