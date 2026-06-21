"""Umlage drilldown preview parity tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest


def _measure(client):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    return client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-12-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]


@pytest.fixture
def umlage(client, db_session, org):
    """Build a full UMLAGE_KOSTENSTELLEN position with key, ziel, source pool, bookings."""
    from app.models.allocation import (
        AllocationKey,
        AllocationKeyPosition,
        UmlageSourceScope,
        UmlageSourceScopeCostCenter,
    )
    from app.models.finanzplan import FinanzplanPosition
    from app.models.master import CostCenter, FiscalYear
    from app.models.transaction import Transaction, TransactionSplit

    measure_id = _measure(client)

    # cost centers: ziel + 2 source
    ziel = CostCenter(org_id=org.id, name="Berlin", code="B-001", typ="PROJECT")
    q1 = CostCenter(org_id=org.id, name="Verwaltung", code="V-001", typ="OVERHEAD")
    q2 = CostCenter(org_id=org.id, name="Leitung", code="V-002", typ="OVERHEAD")
    db_session.add_all([ziel, q1, q2])
    db_session.commit()

    ak = AllocationKey(
        org_id=org.id, name="Schlüssel 2026", basis="MITARBEITERZAHL",
        gueltig_von=date(2026, 1, 1), gueltig_bis=None,
    )
    db_session.add(ak)
    db_session.commit()
    db_session.add(
        AllocationKeyPosition(
            org_id=org.id, allocation_key_id=ak.id, cost_center_id=ziel.id, prozent=Decimal("20"),
        )
    )

    scope = UmlageSourceScope(org_id=org.id, name="GK-Pool", beschreibung="Gemeinkosten")
    db_session.add(scope)
    db_session.commit()
    db_session.add_all([
        UmlageSourceScopeCostCenter(org_id=org.id, umlage_source_scope_id=scope.id, cost_center_id=q1.id),
        UmlageSourceScopeCostCenter(org_id=org.id, umlage_source_scope_id=scope.id, cost_center_id=q2.id),
    ])

    pos = FinanzplanPosition(
        org_id=org.id, funding_measure_id=measure_id, positionscode="9.1",
        bezeichnung="Verwaltungspauschale", betrag_bewilligt=Decimal("5000"),
        ist_pauschale=True, pauschale_typ="UMLAGE_KOSTENSTELLEN",
        umlage_allocation_key_id=ak.id, umlage_ziel_cost_center_id=ziel.id,
        umlage_source_scope_id=scope.id,
    )
    db_session.add(pos)

    fy = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(fy)
    db_session.commit()

    # two bookings on q1 (1000) and q2 (2000) gross
    for cc, amount in ((q1, "1000"), (q2, "2000")):
        tx = Transaction(
            org_id=org.id, fiscal_year_id=fy.id, datum=date(2026, 3, 1),
            betrag=Decimal(f"-{amount}"), typ="AUSGABE",
        )
        db_session.add(tx)
        db_session.commit()
        db_session.add(
            TransactionSplit(
                org_id=org.id, transaction_id=tx.id, cost_center_id=cc.id,
                prozent=Decimal("100"), betrag_anteil=Decimal(f"-{amount}"),
            )
        )
    db_session.commit()

    return {"measure": measure_id, "position": pos.id}


def test_umlage_preview(client, umlage):
    r = client.get(
        f"/api/protected/foerdermassnahmen/{umlage['measure']}"
        f"/finanzplan-positionen/{umlage['position']}/umlage-preview"
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["position"]["positionscode"] == "9.1"
    assert d["position"]["betrag_bewilligt"] == 5000
    assert d["ziel_kostenstelle"]["anteil_prozent"] == 20
    assert d["quell_pool"]["name"] == "GK-Pool"
    assert len(d["quell_pool"]["cost_centers"]) == 2
    b = d["berechnung"]
    # (1000 + 2000) * 20% = 600 brutto umgelegt
    assert b["brutto_umgelegt"] == pytest.approx(600.0)
    # mwst not foerderfahig by default → netto; foerderquote 80%
    assert b["foerderquote"] == 80
    assert b["betrag_foerderfahig"] > 0
    assert b["cap_bewilligt"] == 5000
    # per-kostenstelle: V-001=200, V-002=400
    per = {x["quell_cc_code"]: x["brutto_summe"] for x in b["per_kostenstelle"]}
    assert per["V-001"] == pytest.approx(200.0)
    assert per["V-002"] == pytest.approx(400.0)


def test_umlage_preview_not_found(client):
    mid = _measure(client)
    r = client.get(
        f"/api/protected/foerdermassnahmen/{mid}/finanzplan-positionen/nope/umlage-preview"
    )
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_umlage_preview_not_umlage(client, db_session, org):
    from app.models.finanzplan import FinanzplanPosition

    mid = _measure(client)
    pos = FinanzplanPosition(
        org_id=org.id, funding_measure_id=mid, positionscode="1.1",
        bezeichnung="Normal", betrag_bewilligt=Decimal("1000"),
    )
    db_session.add(pos)
    db_session.commit()
    r = client.get(
        f"/api/protected/foerdermassnahmen/{mid}/finanzplan-positionen/{pos.id}/umlage-preview"
    )
    assert r.status_code == 400 and r.json()["code"] == "NOT_UMLAGE"


def test_umlage_preview_incomplete(client, db_session, org):
    from app.models.finanzplan import FinanzplanPosition

    mid = _measure(client)
    pos = FinanzplanPosition(
        org_id=org.id, funding_measure_id=mid, positionscode="9.1",
        bezeichnung="Pauschale ohne Config", betrag_bewilligt=Decimal("1000"),
        ist_pauschale=True, pauschale_typ="UMLAGE_KOSTENSTELLEN",
    )
    db_session.add(pos)
    db_session.commit()
    r = client.get(
        f"/api/protected/foerdermassnahmen/{mid}/finanzplan-positionen/{pos.id}/umlage-preview"
    )
    assert r.status_code == 422 and r.json()["code"] == "INCOMPLETE_UMLAGE"
