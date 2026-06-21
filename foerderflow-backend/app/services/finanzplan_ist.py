"""IST aggregation per FinanzplanPosition — port of lib/finanzplan-ist.ts.

Two-phase: (1) direct allocations via the canonical resolver (non-pauschale),
(2) pauschale positions (FIXER_BETRAG / PROZENT_GESAMT / PROZENT_PERSONAL /
UMLAGE_KOSTENSTELLEN) capped at betrag_bewilligt.
"""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.allocation import (
    AllocationKey,
    AllocationKeyPosition,
    UmlageSourceScopeCostCenter,
)
from app.models.enums import PauschaleTyp
from app.models.finanzplan import FinanzplanPosition, FinanzplanPositionKostenbereich
from app.models.funding import FundingMeasure
from app.models.master import Kostenbereich
from app.models.transaction import Transaction, TransactionSplit
from app.services.allocation_betraege import compute_allocation_betraege
from app.services.allocation_position_resolver import allocation_to_position_subquery


def _ev(v):
    return v.value if hasattr(v, "value") else v


def aggregate_ist_by_finanzplan_position(
    db: Session, funding_measure_id: str, org_id: str
) -> dict[str, float]:
    # Phase 1 — direct allocations via resolver, excluding pauschale positions.
    resolved = allocation_to_position_subquery(funding_measure_id, org_id)
    rows = db.execute(
        select(
            resolved.c.effective_finanzplan_position_id,
            func.coalesce(func.sum(resolved.c.gewichteter_betrag), 0),
        )
        .select_from(resolved)
        .join(
            FinanzplanPosition,
            FinanzplanPosition.id == resolved.c.effective_finanzplan_position_id,
        )
        .where(FinanzplanPosition.ist_pauschale.is_(False))
        .group_by(resolved.c.effective_finanzplan_position_id)
    ).all()
    result: dict[str, float] = {pid: float(s or 0) for pid, s in rows}

    _compute_pauschale_positionen(db, funding_measure_id, org_id, result)
    return result


def _compute_pauschale_positionen(
    db: Session, funding_measure_id: str, org_id: str, phase1: dict[str, float]
) -> None:
    pauschale = (
        db.execute(
            select(FinanzplanPosition).where(
                FinanzplanPosition.funding_measure_id == funding_measure_id,
                FinanzplanPosition.org_id == org_id,
                FinanzplanPosition.ist_pauschale.is_(True),
            )
        )
        .scalars()
        .all()
    )
    if not pauschale:
        return

    measure = db.execute(
        select(FundingMeasure).where(
            FundingMeasure.id == funding_measure_id, FundingMeasure.org_id == org_id
        )
    ).scalar_one_or_none()
    default_prozent = (
        float(measure.verwaltungspauschale_prozent)
        if measure and measure.verwaltungspauschale_prozent is not None
        else None
    )

    personal_position_ids: set[str] | None = None
    if any(_ev(p.pauschale_typ) == "PROZENT_PERSONAL" for p in pauschale):
        prows = db.execute(
            select(FinanzplanPositionKostenbereich.finanzplan_position_id)
            .join(Kostenbereich, Kostenbereich.id == FinanzplanPositionKostenbereich.kostenbereich_id)
            .join(
                FinanzplanPosition,
                FinanzplanPosition.id == FinanzplanPositionKostenbereich.finanzplan_position_id,
            )
            .where(
                FinanzplanPosition.funding_measure_id == funding_measure_id,
                FinanzplanPosition.org_id == org_id,
                FinanzplanPosition.ist_pauschale.is_(False),
                Kostenbereich.ist_personal.is_(True),
            )
            .distinct()
        ).all()
        personal_position_ids = {r[0] for r in prows}

    for pos in pauschale:
        cap = float(pos.betrag_bewilligt)
        prozent = float(pos.pauschale_prozent) if pos.pauschale_prozent is not None else default_prozent
        typ = _ev(pos.pauschale_typ)

        if typ == "FIXER_BETRAG":
            berechnet = cap
        elif typ == "PROZENT_GESAMT":
            if prozent is None:
                berechnet = 0.0
            else:
                basis = sum(v for pid, v in phase1.items() if pid != pos.id)
                berechnet = basis * prozent / 100
        elif typ == "PROZENT_PERSONAL":
            if prozent is None or personal_position_ids is None:
                berechnet = 0.0
            else:
                basis = sum(phase1.get(pid, 0.0) for pid in personal_position_ids)
                berechnet = basis * prozent / 100
        elif typ == "UMLAGE_KOSTENSTELLEN":
            berechnet = _compute_umlage(db, org_id, pos, measure)
        else:
            continue

        phase1[pos.id] = min(max(0.0, berechnet), cap)


def _compute_umlage(db: Session, org_id: str, pos: FinanzplanPosition, measure) -> float:
    if (
        not pos.umlage_allocation_key_id
        or not pos.umlage_ziel_cost_center_id
        or not pos.umlage_source_scope_id
        or measure is None
    ):
        return 0.0
    ref = db.execute(
        select(AllocationKey).where(
            AllocationKey.id == pos.umlage_allocation_key_id, AllocationKey.org_id == org_id
        )
    ).scalar_one_or_none()
    if ref is None:
        return 0.0
    family_root = ref.parent_key_id or ref.id

    brutto = db.execute(
        select(
            func.coalesce(func.sum(func.abs(TransactionSplit.betrag_anteil) * AllocationKeyPosition.prozent / 100), 0)
        )
        .select_from(Transaction)
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .join(
            UmlageSourceScopeCostCenter,
            and_(
                UmlageSourceScopeCostCenter.cost_center_id == TransactionSplit.cost_center_id,
                UmlageSourceScopeCostCenter.umlage_source_scope_id == pos.umlage_source_scope_id,
            ),
        )
        .join(
            AllocationKey,
            and_(
                AllocationKey.org_id == org_id,
                or_(AllocationKey.id == family_root, AllocationKey.parent_key_id == family_root),
                Transaction.datum >= AllocationKey.gueltig_von,
                or_(AllocationKey.gueltig_bis.is_(None), Transaction.datum <= AllocationKey.gueltig_bis),
            ),
        )
        .join(
            AllocationKeyPosition,
            and_(
                AllocationKeyPosition.allocation_key_id == AllocationKey.id,
                AllocationKeyPosition.cost_center_id == pos.umlage_ziel_cost_center_id,
            ),
        )
        .where(Transaction.org_id == org_id)
    ).scalar_one()

    betraege = compute_allocation_betraege(
        float(brutto or 0),
        float(measure.foerderquote),
        measure.mwst_foerderfahig,
        float(measure.mwst_satz_prozent),
    )
    return betraege.betrag_foerderfahig
