"""Massnahme-Zuordnung — port of lib/massnahme-zuordnung.ts.

Assigns a measure to ALL splits of a transaction (one VORLAEUFIG FundAllocation
per split). Validates measure ownership, transaction has splits, datum within
Laufzeit, and the measure's cost-center whitelist (empty = wildcard). Returns
ok/reason (never raises) for batch collection. Checks run BEFORE any mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.funding import FundingMeasure
from app.models.transaction import FundAllocation, Transaction, TransactionSplit
from app.services.allocation_betraege import compute_allocation_betraege


@dataclass
class MassnahmeContext:
    foerderquote: float
    mwst_foerderfahig: bool
    mwst_satz: float
    laufzeit_von: date
    laufzeit_bis: date
    cost_center_ids: list[str] = field(default_factory=list)


@dataclass
class AssignResult:
    ok: bool
    id: str
    reason: str | None = None


def load_massnahme_context(db: Session, org_id: str, funding_measure_id: str) -> MassnahmeContext | None:
    m = db.execute(
        select(FundingMeasure)
        .where(FundingMeasure.id == funding_measure_id, FundingMeasure.org_id == org_id)
        .options(selectinload(FundingMeasure.cost_centers))
    ).scalar_one_or_none()
    if m is None:
        return None
    return MassnahmeContext(
        foerderquote=float(m.foerderquote),
        mwst_foerderfahig=m.mwst_foerderfahig,
        mwst_satz=float(m.mwst_satz_prozent),
        laufzeit_von=m.laufzeit_von,
        laufzeit_bis=m.laufzeit_bis,
        cost_center_ids=[cc.cost_center_id for cc in m.cost_centers],
    )


def _fmt_date(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def assign_massnahme_to_transaction(
    db: Session,
    org_id: str,
    transaction_id: str,
    funding_measure_id: str,
    context: MassnahmeContext,
) -> AssignResult:
    tx = db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.org_id == org_id)
        .options(selectinload(Transaction.splits))
    ).scalar_one_or_none()
    if tx is None:
        return AssignResult(False, transaction_id, "Transaktion nicht gefunden.")
    if not tx.splits:
        return AssignResult(
            False,
            transaction_id,
            "Keine KST-Splits vorhanden. Bitte zuerst Kostenstellen zuordnen.",
        )
    if tx.datum < context.laufzeit_von or tx.datum > context.laufzeit_bis:
        return AssignResult(
            False,
            transaction_id,
            f"Transaktionsdatum ({_fmt_date(tx.datum)}) außerhalb der Bewilligungslaufzeit "
            f"({_fmt_date(context.laufzeit_von)} – {_fmt_date(context.laufzeit_bis)}).",
        )
    if context.cost_center_ids:
        tx_kst = [s.cost_center_id for s in tx.splits]
        if not all(k in context.cost_center_ids for k in tx_kst):
            return AssignResult(
                False,
                transaction_id,
                "Kostenstelle(n) der Transaktion sind nicht für diese Fördermassnahme "
                "freigegeben.",
            )

    # remove existing allocations on these splits, then create one per split
    split_ids = [s.id for s in tx.splits]
    db.query(FundAllocation).filter(
        FundAllocation.transaction_split_id.in_(split_ids)
    ).delete(synchronize_session=False)
    for split in tx.splits:
        b = compute_allocation_betraege(
            abs(float(split.betrag_anteil)),
            context.foerderquote,
            context.mwst_foerderfahig,
            context.mwst_satz,
        )
        db.add(
            FundAllocation(
                org_id=org_id,
                transaction_split_id=split.id,
                funding_measure_id=funding_measure_id,
                prozent=100,
                betrag_foerderfahig=b.betrag_foerderfahig,
                betrag_foerderung=b.betrag_foerderung,
                betrag_eigenanteil=b.betrag_eigenanteil,
                status="VORLAEUFIG",
            )
        )
    tx.status = "ZUGEORDNET"
    db.commit()
    return AssignResult(True, transaction_id)
