"""Ampel / Prognose / Preflight parity tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.ampel import berechne_ampel
from app.services.jahresendprognose import berechne_jahresendprognose


@pytest.fixture
def measure(client):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    return client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]


# ── pure ──────────────────────────────────────────────────────────────────────
def test_prognose_pure():
    today = date.today()
    r = berechne_jahresendprognose(
        laufzeit_bis=today + timedelta(days=180),
        allocations=[{"datum": today - timedelta(days=10), "betrag_foerderfahig": 3000}],
        betrag_bewilligt=10000,
    )
    assert r.betrag_ist_gesamt == 3000
    assert r.monatsrate == 1000.0  # 3000 / 3
    assert r.days_remaining == 180


def test_ampel_pure_overhead():
    today = date.today()
    r = berechne_ampel(
        betrag_bewilligt=1000, betrag_ist=100, laufzeit_von=today, laufzeit_bis=today + timedelta(days=300),
        overhead_limit_prozent=10, overhead_ist_prozent=15,
    )
    assert r.status == "ROT"
    assert "Gemeinkostendeckel" in r.gruende[0]


# ── endpoints ─────────────────────────────────────────────────────────────────
def test_ampel_endpoint(client, measure):
    r = client.get(f"/api/protected/foerdermassnahmen/{measure}/ampel")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert "status" in d and "gruende" in d
    assert d["betrag_ist"] == "0"
    assert d["betrag_bewilligt"] == "100000"


def test_prognose_endpoint(client, measure):
    r = client.get(f"/api/protected/foerdermassnahmen/{measure}/prognose")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["betrag_ist_gesamt"] == 0
    assert d["betrag_bewilligt"] == "100000.00"
    assert d["status"] == "UNTERAUSSCHOEPFUNG"  # nothing spent


def test_preflight_endpoint(client, measure):
    r = client.get(f"/api/protected/foerdermassnahmen/{measure}/preflight")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["total_tx"] == 0
    assert d["positions_total"] == 0
    assert d["ready"] is True  # no unassigned, no orange, no positions
    assert "drilldowns" in d


def test_analytics_not_found(client):
    for ep in ("ampel", "prognose", "preflight"):
        r = client.get(f"/api/protected/foerdermassnahmen/nope/{ep}")
        assert r.status_code == 404
