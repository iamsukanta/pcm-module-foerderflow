"""Finanzplan grid parity tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def setup(client):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-03-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    # systemweiter kostenbereich + bridge
    return {"measure": mid, "funder": fid}


def _kostenbereich(db_session):
    from app.models.master import Kostenbereich

    kb = Kostenbereich(code="PERSONAL", bezeichnung="Personalkosten", ist_personal=True)
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    return kb.id


def test_grid_structure(client, setup, db_session):
    kb_id = _kostenbereich(db_session)
    pid = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": setup["measure"], "positionscode": "1.1",
            "bezeichnung": "Personal", "betrag_bewilligt": 30000,
            "kostenbereiche": [{"kostenbereich_id": kb_id}],
        },
    ).json()["data"]["id"]

    r = client.get(f"/api/protected/foerdermassnahmen/{setup['measure']}/finanzplan")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    # Jan, Feb, Mar
    assert d["laufzeit_monate"] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert len(d["positionen"]) == 1
    assert d["gesamt_bewilligt"] == "30000.00"
    assert d["positionen"][0]["kostenbereiche"][0]["kostenbereich_code"] == "PERSONAL"


def test_grid_batch_upsert_and_delete(client, setup, db_session):
    kb_id = _kostenbereich(db_session)
    pid = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": setup["measure"], "positionscode": "1.1",
            "bezeichnung": "Personal", "betrag_bewilligt": 30000,
            "kostenbereiche": [{"kostenbereich_id": kb_id}],
        },
    ).json()["data"]["id"]

    r = client.post(
        f"/api/protected/foerdermassnahmen/{setup['measure']}/finanzplan",
        json={"updates": [
            {"finanzplan_position_id": pid, "kostenbereich_id": kb_id, "fuer_monat": "2026-01-01", "betrag_geplant": "10000"},
            {"finanzplan_position_id": pid, "kostenbereich_id": kb_id, "fuer_monat": "2026-02-01", "betrag_geplant": "10000"},
        ]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["updated"] == 2

    grid = client.get(f"/api/protected/foerdermassnahmen/{setup['measure']}/finanzplan").json()["data"]
    assert grid["gesamt_geplant"] == "20000.00"
    assert grid["diff"] == "10000.00"

    # betrag 0 deletes
    r = client.post(
        f"/api/protected/foerdermassnahmen/{setup['measure']}/finanzplan",
        json={"updates": [
            {"finanzplan_position_id": pid, "kostenbereich_id": kb_id, "fuer_monat": "2026-01-01", "betrag_geplant": "0"},
        ]},
    )
    assert r.json()["data"]["deleted"] == 1


def test_grid_validation(client, setup, db_session):
    kb_id = _kostenbereich(db_session)
    pid = client.post(
        "/api/protected/finanzplan-positionen",
        json={
            "funding_measure_id": setup["measure"], "positionscode": "1.1",
            "bezeichnung": "Personal", "betrag_bewilligt": 30000,
            "kostenbereiche": [{"kostenbereich_id": kb_id}],
        },
    ).json()["data"]["id"]
    # not month-first
    r = client.post(
        f"/api/protected/foerdermassnahmen/{setup['measure']}/finanzplan",
        json={"updates": [
            {"finanzplan_position_id": pid, "kostenbereich_id": kb_id, "fuer_monat": "2026-01-15", "betrag_geplant": "100"},
        ]},
    )
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_personalmodul_stub(client, setup):
    r = client.post(f"/api/protected/foerdermassnahmen/{setup['measure']}/finanzplan/personalmodul")
    assert r.status_code == 422 and r.json()["code"] == "KST_MAPPING_REQUIRED"


def test_grid_not_found(client):
    r = client.get("/api/protected/foerdermassnahmen/nope/finanzplan")
    assert r.status_code == 404
