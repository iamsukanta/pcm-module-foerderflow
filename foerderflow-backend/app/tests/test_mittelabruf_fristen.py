"""Mittelabruf + Fristen + Fehlbedarf-compliance parity tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.fehlbedarf_compliance import compute_fehlbedarf_status, ist_compliance_relevant
from app.services.fristen_service import dringlichkeit, get_frist_status


@pytest.fixture
def base(client):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    hjid = client.post(
        "/api/protected/haushaltsjahre",
        json={"jahr": 2026, "beginn": "2026-01-01", "ende": "2026-12-31"},
    ).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31",
            "mittelabruf_verfahren": "ANFORDERUNG",
        },
    ).json()["data"]["id"]
    return {"funder": fid, "hj": hjid, "measure": mid}


# ── pure compliance tests ─────────────────────────────────────────────────────
def test_compliance_relevance():
    assert ist_compliance_relevant("FEHLBEDARF", 50) is True
    assert ist_compliance_relevant("FESTBETRAG", 100) is True
    assert ist_compliance_relevant("FESTBETRAG", 80) is False
    assert ist_compliance_relevant("ANTEIL", 80) is False


def test_compute_fehlbedarf_warnung():
    r = compute_fehlbedarf_status(
        finanzierungsart="FEHLBEDARF", foerderquote=70,
        gesamtausgaben_plan=100000, eigenmittel_plan=10000, drittmittel_plan=0,
        zuwendung_hoechstbetrag=90000, eigenmittel_ist=10000, drittmittel_ist=0,
        zuwendung_abgerufen=95000,
    )
    assert r["status"] == "WARNUNG" and r["meldepflichtig"] is True
    assert r["fehlbedarf_zulaessig"] == 90000


def test_compute_fehlbedarf_none_for_anteil():
    assert compute_fehlbedarf_status(
        finanzierungsart="ANTEIL", foerderquote=80, gesamtausgaben_plan=1, eigenmittel_plan=0,
        drittmittel_plan=0, zuwendung_hoechstbetrag=1, eigenmittel_ist=0, drittmittel_ist=0,
        zuwendung_abgerufen=0,
    ) is None


def test_frist_status_helpers():
    today = date.today()
    assert get_frist_status(today + timedelta(days=3), "ABGERUFEN") == "KRITISCH"
    assert get_frist_status(today + timedelta(days=10), "ABGERUFEN") == "WARNING"
    assert get_frist_status(today + timedelta(days=30), "ABGERUFEN") == "OK"
    assert get_frist_status(today - timedelta(days=1), "ABGERUFEN") == "ABGELAUFEN"
    assert get_frist_status(today - timedelta(days=1), "VERWENDET") == "OK"
    assert dringlichkeit(5) == "KRITISCH" and dringlichkeit(10) == "WARNUNG" and dringlichkeit(30) == "OK"


# ── endpoint tests ────────────────────────────────────────────────────────────
def test_create_list_get_mittelabruf(client, base):
    r = client.post(
        "/api/protected/mittelabrufe",
        json={
            "funding_measure_id": base["measure"], "fiscal_year_id": base["hj"],
            "abruf_datum": "2026-03-01", "betrag": 5000,
        },
    )
    assert r.status_code == 201, r.text
    m = r.json()["data"]
    assert m["betrag"] == "5000"
    assert m["verwendungsfrist_tage"] == 42
    assert m["frist_bis"] == "2026-04-12"  # 2026-03-01 + 42 days
    mid = m["id"]

    r = client.get("/api/protected/mittelabrufe")
    assert len(r.json()["data"]) == 1

    r = client.get(f"/api/protected/mittelabrufe/{mid}")
    assert r.status_code == 200
    assert "tage_verbleibend" in r.json()["data"]
    assert "frist_status" in r.json()["data"]
    assert r.json()["data"]["betrag_offen"] == 5000.0


def test_mittelabruf_abruf_verfahren_rejected(client):
    fid = client.post("/api/protected/funder", json={"name": "F2", "typ": "STIFTUNG"}).json()["data"]["id"]
    hjid = client.post(
        "/api/protected/haushaltsjahre",
        json={"jahr": 2027, "beginn": "2027-01-01", "ende": "2027-12-31"},
    ).json()["data"]["id"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "ABRUF-M", "budget_gesamt": 1000, "foerderquote": 100,
            "laufzeit_von": "2027-01-01", "laufzeit_bis": "2027-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]
    r = client.post(
        "/api/protected/mittelabrufe",
        json={"funding_measure_id": mid, "fiscal_year_id": hjid, "abruf_datum": "2027-03-01", "betrag": 100},
    )
    assert r.status_code == 400 and r.json()["code"] == "ABRUF_VERFAHREN_NOT_SUPPORTED"


def test_mittelabruf_validation(client, base):
    r = client.post(
        "/api/protected/mittelabrufe",
        json={"funding_measure_id": base["measure"], "fiscal_year_id": base["hj"],
              "abruf_datum": "2026-03-01", "betrag": -5},
    )
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_BETRAG"


def test_mittelabruf_compliance_block(client, base):
    # FEHLBEDARF measure: budget 10000, eigen 2000, dritt 0 -> hoechstbetrag 8000
    fid = base["funder"]
    mid = client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Fehlbedarf-M", "budget_gesamt": 10000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ANFORDERUNG",
            "finanzierungsart": "FEHLBEDARF", "eigenmittel_betrag": 2000,
        },
    ).json()["data"]["id"]
    # abruf 9000 > verbleibend 8000 -> blocked
    r = client.post(
        "/api/protected/mittelabrufe",
        json={"funding_measure_id": mid, "fiscal_year_id": base["hj"], "abruf_datum": "2026-03-01", "betrag": 9000},
    )
    assert r.status_code == 422 and r.json()["code"] == "MITTELABRUF_LIMIT_UEBERSCHRITTEN"
    # abruf 8000 ok
    r = client.post(
        "/api/protected/mittelabrufe",
        json={"funding_measure_id": mid, "fiscal_year_id": base["hj"], "abruf_datum": "2026-03-01", "betrag": 8000},
    )
    assert r.status_code == 201


def test_update_and_frist(client, base):
    mid = client.post(
        "/api/protected/mittelabrufe",
        json={"funding_measure_id": base["measure"], "fiscal_year_id": base["hj"],
              "abruf_datum": "2026-03-01", "betrag": 5000},
    ).json()["data"]["id"]

    # change frist (status ABGERUFEN)
    r = client.patch(f"/api/protected/mittelabrufe/{mid}/frist", json={"verwendungsfrist_tage": 30})
    assert r.status_code == 200
    assert r.json()["data"]["frist_bis"] == "2026-03-31"

    # mark VERWENDET requires betrag_verwendet >= betrag
    r = client.patch(f"/api/protected/mittelabrufe/{mid}", json={"status": "VERWENDET", "betrag_verwendet": 5000})
    assert r.status_code == 200 and r.json()["data"]["status"] == "VERWENDET"
    # frist change now blocked (status != ABGERUFEN)
    r = client.patch(f"/api/protected/mittelabrufe/{mid}/frist", json={"verwendungsfrist_tage": 20})
    assert r.status_code == 400 and r.json()["code"] == "STATUS_NOT_ABGERUFEN"


def test_kalender(client, base):
    client.post(
        "/api/protected/mittelabrufe",
        json={"funding_measure_id": base["measure"], "fiscal_year_id": base["hj"],
              "abruf_datum": "2026-03-01", "betrag": 5000},
    )
    r = client.get(f"/api/protected/mittelabrufe/kalender?haushaltsjahr_id={base['hj']}&periode=MONAT")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["haushaltsjahr"]["jahr"] == 2026
    assert len(d["perioden"]) == 1
    assert d["perioden"][0]["gesamt_abgerufen"] == "5000.00"


def test_fristen(client, base):
    client.post(
        "/api/protected/mittelabrufe",
        json={"funding_measure_id": base["measure"], "fiscal_year_id": base["hj"],
              "abruf_datum": "2026-03-01", "betrag": 5000},
    )
    r = client.get("/api/protected/fristen?days_ahead=365")
    assert r.status_code == 200
    typen = {item["typ"] for item in r.json()["data"]}
    assert "MITTELABRUF" in typen

    r = client.get("/api/protected/fristen?days_ahead=500")
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_DAYS_AHEAD"


def test_kritische_count(client, base):
    r = client.get("/api/protected/fristen/kritische-count")
    assert r.status_code == 200, r.text
    assert "count" in r.json()["data"]
    assert isinstance(r.json()["data"]["count"], int)


def test_fehlbedarf_status_endpoint(client, base):
    # ANTEIL measure -> not compliance relevant
    r = client.get(f"/api/protected/foerdermassnahmen/{base['measure']}/fehlbedarf-status")
    assert r.status_code == 200
    assert r.json()["data"]["status"]["active"] is False


def test_compliance_dismiss(client):
    r = client.post("/api/protected/compliance/dismiss", json={"alertHash": "abc123"})
    assert r.status_code == 200 and r.json()["ok"] is True
    r = client.post("/api/protected/compliance/dismiss", json={})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ALERT_HASH"
