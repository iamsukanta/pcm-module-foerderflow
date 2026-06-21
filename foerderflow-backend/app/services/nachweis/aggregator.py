"""build_nachweis_data — port of lib/nachweis/aggregator.ts.

Aggregates the NachweisData snapshot: Einnahmen (zuwendung/eigenmittel from
allocations, prozent-weighted), Ausgaben grouped by Kostenbereich (personal vs.
sach via ist_personal), deduplicated transaction list, and the Soll-Ist budget
positions via the canonical IST aggregator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.funding import FundingMeasure
from app.models.master import FiscalYear
from app.models.organization import Organization
from app.models.transaction import FundAllocation, Transaction, TransactionSplit
from app.services.finanzplan_ist import aggregate_ist_by_finanzplan_position

KEY_OHNE_ZUORDNUNG = "__OHNE_ZUORDNUNG__"
LABEL_OHNE_ZUORDNUNG = "Sonstige Ausgaben"


def build_nachweis_data(
    db: Session, funding_measure_id: str, fiscal_year_id: str, org_id: str
) -> dict[str, Any]:
    measure = db.execute(
        select(FundingMeasure)
        .where(FundingMeasure.id == funding_measure_id, FundingMeasure.org_id == org_id)
        .options(
            selectinload(FundingMeasure.funder),
            selectinload(FundingMeasure.finanzplan_positionen),
        )
    ).scalar_one_or_none()
    if measure is None:
        raise ValueError("Fördermassnahme nicht gefunden")
    fy = db.execute(
        select(FiscalYear).where(FiscalYear.id == fiscal_year_id, FiscalYear.org_id == org_id)
    ).scalar_one_or_none()
    if fy is None:
        raise ValueError("Haushaltsjahr nicht gefunden")
    org = db.get(Organization, org_id)
    if org is None:
        raise ValueError("Organisation nicht gefunden")

    allocations = (
        db.execute(
            select(FundAllocation)
            .join(TransactionSplit, TransactionSplit.id == FundAllocation.transaction_split_id)
            .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
            .where(
                FundAllocation.funding_measure_id == funding_measure_id,
                FundAllocation.org_id == org_id,
                Transaction.fiscal_year_id == fiscal_year_id,
                Transaction.org_id == org_id,
            )
            .options(
                selectinload(FundAllocation.transaction_split)
                .selectinload(TransactionSplit.transaction)
                .selectinload(Transaction.kostenbereich),
                selectinload(FundAllocation.transaction_split)
                .selectinload(TransactionSplit.transaction)
                .selectinload(Transaction.belege),
                selectinload(FundAllocation.transaction_split).selectinload(
                    TransactionSplit.allocation_key
                ),
            )
        )
        .scalars()
        .all()
    )

    zuwendung = 0.0
    eigenmittel = 0.0
    ausgaben_map: dict[str, dict[str, Any]] = {}
    transaktion_map: dict[str, dict[str, Any]] = {}

    for alloc in allocations:
        split = alloc.transaction_split
        tx = split.transaction
        f = float(alloc.prozent) / 100
        zuwendung += float(alloc.betrag_foerderung) * f
        eigenmittel += float(alloc.betrag_eigenanteil) * f

        kb = tx.kostenbereich
        kb_id = kb.id if kb else KEY_OHNE_ZUORDNUNG
        kb_bez = kb.bezeichnung if kb else LABEL_OHNE_ZUORDNUNG
        kb_code = kb.code if kb else None
        kb_personal = kb.ist_personal if kb else False
        foerderung_betrag = float(alloc.betrag_foerderung) * f
        foerderfahig_betrag = float(alloc.betrag_foerderfahig) * f
        belege_count = len([b for b in tx.belege if b.geloescht_am is None])
        anteil_beschreibung = split.allocation_key.name if split.allocation_key else None

        existing = ausgaben_map.get(kb_id)
        if existing:
            existing["betrag_foerderfahig"] += foerderfahig_betrag
            existing["belege_count"] += belege_count
        else:
            ausgaben_map[kb_id] = {
                "kostenart": kb_bez,
                "kostenbereich_code": kb_code,
                "ist_personal": kb_personal,
                "betrag_foerderfahig": foerderfahig_betrag,
                "anteil_beschreibung": anteil_beschreibung,
                "belege_count": belege_count,
            }

        existing_tx = transaktion_map.get(tx.id)
        if existing_tx:
            existing_tx["betrag_foerderung"] += foerderung_betrag
        else:
            transaktion_map[tx.id] = {
                "datum": tx.datum.isoformat(),
                "auftraggeber": tx.auftraggeber,
                "verwendungszweck": tx.verwendungszweck,
                "betrag": float(tx.betrag),
                "betrag_foerderung": foerderung_betrag,
                "kostenart": kb.bezeichnung if kb else None,
                "belege_count": belege_count,
            }

    budget_positionen: list[dict[str, Any]] = []
    if measure.finanzplan_positionen:
        ist_by_position = aggregate_ist_by_finanzplan_position(db, funding_measure_id, org_id)
        for pos in sorted(measure.finanzplan_positionen, key=lambda p: p.sort_order):
            ist = ist_by_position.get(pos.id, 0.0)
            bewilligt = float(pos.betrag_bewilligt)
            budget_positionen.append(
                {
                    "kostenart": f"{pos.positionscode}: {pos.bezeichnung}",
                    "kostenbereich_code": None,
                    "betrag_bewilligt": bewilligt,
                    "betrag_ist": ist,
                    "differenz": bewilligt - ist,
                }
            )

    ausgaben = list(ausgaben_map.values())
    gesamt_foerderfahig = sum(v["betrag_foerderfahig"] for v in ausgaben)

    return {
        "massnahme": {
            "name": measure.name,
            "foerderquote": float(measure.foerderquote),
            "budget_gesamt": float(measure.budget_gesamt),
            "laufzeit_von": measure.laufzeit_von.isoformat(),
            "laufzeit_bis": measure.laufzeit_bis.isoformat(),
            "funder_name": measure.funder.name,
        },
        "fiscal_year": {
            "jahr": fy.jahr,
            "beginn": fy.beginn.isoformat(),
            "ende": fy.ende.isoformat(),
        },
        "org": {"name": org.name},
        "einnahmen": {"eigenmittel": eigenmittel, "zuwendung": zuwendung, "sonstige": 0},
        "ausgaben": ausgaben,
        "gesamt_foerderfahig": gesamt_foerderfahig,
        "budget_positionen": budget_positionen,
        "transaktionen": sorted(transaktion_map.values(), key=lambda t: t["datum"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
