"""Booking-rule engine parity tests (CRUD, preview, suggest, backfill, batch)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.master import FiscalYear
from app.models.transaction import Transaction


@pytest.fixture
def base(client, db_session, org):
    cc = client.post(
        "/api/protected/kostenstellen", json={"name": "Projekt", "code": "P1", "typ": "PROJECT"}
    ).json()["data"]["id"]
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(fy)
    db_session.flush()
    txs = []
    for i in range(3):
        t = Transaction(
            org_id=org.id, fiscal_year_id=fy.id, datum=date(2026, 3, 1 + i),
            betrag=Decimal("-100.00"), typ="AUSGABE", auftraggeber="Telekom Deutschland GmbH",
            verwendungszweck="Internet", status="IMPORTIERT",
        )
        db_session.add(t)
        txs.append(t)
    db_session.commit()
    return {"cc": cc, "measure": mid, "tx_ids": [t.id for t in txs]}


def _rule_payload(cc, measure=None):
    p = {
        "name": "Telekom-Regel",
        "match_auftraggeber": "Telekom",
        "splits": [{"cost_center_id": cc, "prozent": 100}],
    }
    if measure:
        p["funding_measure_id"] = measure
    return p


def test_create_list_validation(client, base):
    r = client.post("/api/protected/buchungsregeln", json=_rule_payload(base["cc"]))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["confidence"] == "ORANGE"
    assert r.json()["data"]["splits"][0]["prozent"] == "100"

    # sum != 100
    bad = _rule_payload(base["cc"])
    bad["splits"] = [{"cost_center_id": base["cc"], "prozent": 50}]
    r = client.post("/api/protected/buchungsregeln", json=bad)
    assert r.status_code == 400 and r.json()["code"] == "SPLIT_SUM_NOT_100"

    # missing name
    r = client.post("/api/protected/buchungsregeln", json={"splits": [{"cost_center_id": base["cc"], "prozent": 100}]})
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_NAME"

    r = client.get("/api/protected/buchungsregeln")
    assert len(r.json()["data"]) == 1


def test_preview(client, base):
    r = client.post(
        "/api/protected/buchungsregeln/preview", json={"match_auftraggeber": "Telekom"}
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["matched_count"] == 3
    assert len(d["sample"]) == 3
    assert d["total_betrag"] == "-300"

    # no conditions -> 422
    r = client.post("/api/protected/buchungsregeln/preview", json={})
    assert r.status_code == 422 and r.json()["code"] == "NO_CONDITIONS"


def test_suggest(client, base):
    r = client.post(
        "/api/protected/buchungsregeln/suggest",
        json={"transaction_ids": base["tx_ids"]},
    )
    assert r.status_code == 200, r.text
    s = r.json()["data"]["suggestion"]
    # all same auftraggeber -> exact match suggestion
    assert s["match_auftraggeber"] == "Telekom Deutschland GmbH"
    assert s["match_auftraggeber_exact"] is True
    assert r.json()["data"]["basis_count"] == 3


def test_patch_toggle_and_delete(client, base):
    rid = client.post("/api/protected/buchungsregeln", json=_rule_payload(base["cc"])).json()["data"]["id"]
    r = client.patch(f"/api/protected/buchungsregeln/{rid}", json={"aktiv": False, "prioritaet": 5})
    assert r.status_code == 200
    assert r.json()["data"]["aktiv"] is False and r.json()["data"]["prioritaet"] == 5
    r = client.delete(f"/api/protected/buchungsregeln/{rid}")
    assert r.status_code == 200 and r.json()["message"] == "Regel gelöscht."


def test_backfill_applies_rule(client, base):
    rid = client.post(
        "/api/protected/buchungsregeln", json=_rule_payload(base["cc"], base["measure"])
    ).json()["data"]["id"]

    # count first
    r = client.get(f"/api/protected/buchungsregeln/{rid}/backfill")
    assert r.json()["data"]["count"] == 3

    r = client.post(f"/api/protected/buchungsregeln/{rid}/backfill")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["matched"] == 3

    # each tx now has split + allocation (measure linked) -> ZUGEORDNET
    d = client.get(f"/api/protected/transaktionen/{base['tx_ids'][0]}").json()["data"]
    assert d["status"] == "ZUGEORDNET"
    assert len(d["splits"]) == 1
    assert d["splits"][0]["fund_allocations"][0]["funding_measure_id"] == base["measure"]

    # rule match_count rose 3 -> confidence GELB (>=2)
    rule = next(r for r in client.get("/api/protected/buchungsregeln").json()["data"] if r["id"] == rid)
    assert rule["match_count"] == 3 and rule["confidence"] == "GELB"


def test_batch_regeln(client, base):
    rid = client.post(
        "/api/protected/buchungsregeln", json=_rule_payload(base["cc"], base["measure"])
    ).json()["data"]["id"]
    r = client.post(
        "/api/protected/transaktionen/batch-regeln",
        json={"rule_id": rid, "transaction_ids": base["tx_ids"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["matched"] == 3
