"""Transaction splits + fund-allocation (Förderzuordnung) parity tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.master import FiscalYear
from app.models.transaction import Transaction


@pytest.fixture
def setup(client, db_session, org):
    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(fy)
    db_session.flush()
    tx = Transaction(
        org_id=org.id, fiscal_year_id=fy.id, datum=date(2026, 3, 1),
        betrag=Decimal("-1000.00"), typ="AUSGABE", auftraggeber="Lieferant",
        status="IMPORTIERT",
    )
    db_session.add(tx)
    db_session.commit()
    cc1 = client.post(
        "/api/protected/kostenstellen", json={"name": "Projekt", "code": "P1", "typ": "PROJECT"}
    ).json()["data"]["id"]
    cc2 = client.post(
        "/api/protected/kostenstellen", json={"name": "Verw", "code": "VW", "typ": "OVERHEAD"}
    ).json()["data"]["id"]
    fid = client.post(
        "/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}
    ).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000,
            "foerderquote": 80, "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31",
            "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    return {"tx": tx.id, "fy": fy.id, "cc1": cc1, "cc2": cc2, "measure": mid}


def test_splits_sum_invariant(client, setup):
    tx = setup["tx"]
    r = client.put(
        f"/api/protected/transaktionen/{tx}/splits",
        json={"splits": [{"cost_center_id": setup["cc1"], "prozent": 50}]},
    )
    assert r.status_code == 400 and r.json()["code"] == "SPLIT_SUM_NOT_100"


def test_splits_rounding_correction(client, setup):
    tx = setup["tx"]
    r = client.put(
        f"/api/protected/transaktionen/{tx}/splits",
        json={
            "splits": [
                {"cost_center_id": setup["cc1"], "prozent": 33.333},
                {"cost_center_id": setup["cc2"], "prozent": 66.667},
            ]
        },
    )
    assert r.status_code == 200, r.text
    splits = r.json()["data"]["splits"]
    betraege = sorted(float(s["betrag_anteil"]) for s in splits)
    # 1000 split 33.333/66.667 -> 333.33 + 666.67 = 1000.00 exactly (rest method)
    assert sum(betraege) == 1000.0
    # status becomes KATEGORISIERT
    assert r.json()["data"]["status"] == "KATEGORISIERT"


def test_fund_allocation_create_and_amounts(client, setup):
    tx = setup["tx"]
    client.put(
        f"/api/protected/transaktionen/{tx}/splits",
        json={"splits": [{"cost_center_id": setup["cc1"], "prozent": 100}]},
    )
    split_id = client.get(f"/api/protected/transaktionen/{tx}").json()["data"]["splits"][0]["id"]

    r = client.post(
        f"/api/protected/transaktionen/{tx}/fund-allocation",
        json={"transaction_split_id": split_id, "funding_measure_id": setup["measure"]},
    )
    assert r.status_code == 201, r.text
    a = r.json()["data"]
    # brutto 1000, quote 80, mwst förderfähig -> förderfähig 1000, förderung 800, eigen 200
    assert a["betrag_foerderfahig"] == "1000"
    assert a["betrag_foerderung"] == "800"
    assert a["betrag_eigenanteil"] == "200"
    # transaction now ZUGEORDNET
    assert client.get(f"/api/protected/transaktionen/{tx}").json()["data"]["status"] == "ZUGEORDNET"


def test_fund_allocation_doppelfinanzierung(client, setup):
    tx = setup["tx"]
    client.put(
        f"/api/protected/transaktionen/{tx}/splits",
        json={"splits": [{"cost_center_id": setup["cc1"], "prozent": 100}]},
    )
    split_id = client.get(f"/api/protected/transaktionen/{tx}").json()["data"]["splits"][0]["id"]
    body = {"transaction_split_id": split_id, "funding_measure_id": setup["measure"]}
    assert client.post(f"/api/protected/transaktionen/{tx}/fund-allocation", json=body).status_code == 201
    r = client.post(f"/api/protected/transaktionen/{tx}/fund-allocation", json=body)
    assert r.status_code == 409 and r.json()["code"] == "DOPPELFINANZIERUNG"


def test_fund_allocation_list_and_delete(client, setup):
    tx = setup["tx"]
    client.put(
        f"/api/protected/transaktionen/{tx}/splits",
        json={"splits": [{"cost_center_id": setup["cc1"], "prozent": 100}]},
    )
    split_id = client.get(f"/api/protected/transaktionen/{tx}").json()["data"]["splits"][0]["id"]
    client.post(
        f"/api/protected/transaktionen/{tx}/fund-allocation",
        json={"transaction_split_id": split_id, "funding_measure_id": setup["measure"]},
    )
    r = client.get(f"/api/protected/transaktionen/{tx}/fund-allocation")
    assert len(r.json()["data"]) == 1
    assert r.json()["data"][0]["funding_measure"]["foerderquote"] == "80"

    r = client.request(
        "DELETE",
        f"/api/protected/transaktionen/{tx}/fund-allocation",
        json={"transaction_split_id": split_id},
    )
    assert r.status_code == 200 and r.json()["data"]["deleted"] is True
    # back to KATEGORISIERT
    assert client.get(f"/api/protected/transaktionen/{tx}").json()["data"]["status"] == "KATEGORISIERT"


def test_fund_allocation_fiscal_year_closed(client, setup, db_session):
    from app.models.master import FiscalYear as FY

    tx = setup["tx"]
    client.put(
        f"/api/protected/transaktionen/{tx}/splits",
        json={"splits": [{"cost_center_id": setup["cc1"], "prozent": 100}]},
    )
    split_id = client.get(f"/api/protected/transaktionen/{tx}").json()["data"]["splits"][0]["id"]
    fy = db_session.get(FY, setup["fy"])
    fy.status = "GESCHLOSSEN"
    db_session.commit()
    r = client.post(
        f"/api/protected/transaktionen/{tx}/fund-allocation",
        json={"transaction_split_id": split_id, "funding_measure_id": setup["measure"]},
    )
    assert r.status_code == 400 and r.json()["code"] == "FISCAL_YEAR_CLOSED"
