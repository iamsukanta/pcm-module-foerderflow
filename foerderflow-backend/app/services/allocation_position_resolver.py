"""Allocation → FinanzplanPosition resolver — port of
lib/allocation-position-resolver.ts (the canonical Soll/Ist mapping path).

`decide_allocation_position` is the pure bridge-match decision used by the
fund-allocation endpoint. `allocation_to_position_subquery` is the canonical
weighted-IST resolver (Override path + Bridge path), used by every place that
maps allocations to positions (Ueberziehung check, Deckungsfähigkeit, finanzplan
IST). Built with SQLAlchemy Core so it runs on both PostgreSQL and the SQLite
test harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, literal, select, union_all
from sqlalchemy.orm import Session, aliased

from app.models.finanzplan import FinanzplanPosition, FinanzplanPositionKostenbereich
from app.models.transaction import FundAllocation, Transaction, TransactionSplit


# ── pure decision (bridge match count) ───────────────────────────────────────
@dataclass
class PositionDecision:
    kind: str  # ok_auto_bridge | ok_with_position | error_kb_not_in_bescheid |
    #            error_multi_position_needed | error_position_not_in_bridge
    position_id: str | None = None
    candidates: list[dict[str, Any]] | None = None


def decide_allocation_position(
    candidates: list[dict[str, Any]], selected_position_id: str | None
) -> PositionDecision:
    if len(candidates) == 0:
        return PositionDecision("error_kb_not_in_bescheid")
    if selected_position_id:
        if not any(c["id"] == selected_position_id for c in candidates):
            return PositionDecision("error_position_not_in_bridge")
        return PositionDecision("ok_with_position", position_id=selected_position_id)
    if len(candidates) > 1:
        return PositionDecision("error_multi_position_needed", candidates=candidates)
    return PositionDecision("ok_auto_bridge", position_id=candidates[0]["id"])


# ── canonical weighted-IST resolver (Override ∪ Bridge) ──────────────────────
def allocation_to_position_subquery(funding_measure_id: str, org_id: str):
    fpk = aliased(FinanzplanPositionKostenbereich)

    weight_override = (
        FundAllocation.betrag_foerderfahig
        * FundAllocation.prozent
        / 100
        * func.coalesce(fpk.foerderfahig_anteil, 1.0)
    )
    override = (
        select(
            FundAllocation.id.label("allocation_id"),
            FundAllocation.funding_measure_id.label("funding_measure_id"),
            FundAllocation.org_id.label("org_id"),
            FundAllocation.finanzplan_position_id.label("effective_finanzplan_position_id"),
            weight_override.label("gewichteter_betrag"),
        )
        .select_from(FundAllocation)
        .join(TransactionSplit, TransactionSplit.id == FundAllocation.transaction_split_id)
        .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
        .outerjoin(
            fpk,
            and_(
                fpk.finanzplan_position_id == FundAllocation.finanzplan_position_id,
                fpk.kostenbereich_id == Transaction.kostenbereich_id,
            ),
        )
        .where(
            FundAllocation.funding_measure_id == funding_measure_id,
            FundAllocation.org_id == org_id,
            FundAllocation.finanzplan_position_id.is_not(None),
        )
    )

    fpk2 = aliased(FinanzplanPositionKostenbereich)
    weight_bridge = (
        FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100 * fpk2.foerderfahig_anteil
    )
    bridge = (
        select(
            FundAllocation.id.label("allocation_id"),
            FundAllocation.funding_measure_id.label("funding_measure_id"),
            FundAllocation.org_id.label("org_id"),
            fpk2.finanzplan_position_id.label("effective_finanzplan_position_id"),
            weight_bridge.label("gewichteter_betrag"),
        )
        .select_from(FundAllocation)
        .join(TransactionSplit, TransactionSplit.id == FundAllocation.transaction_split_id)
        .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
        .join(fpk2, fpk2.kostenbereich_id == Transaction.kostenbereich_id)
        .join(
            FinanzplanPosition,
            and_(
                FinanzplanPosition.id == fpk2.finanzplan_position_id,
                FinanzplanPosition.funding_measure_id == FundAllocation.funding_measure_id,
            ),
        )
        .where(
            FundAllocation.funding_measure_id == funding_measure_id,
            FundAllocation.org_id == org_id,
            FundAllocation.finanzplan_position_id.is_(None),
        )
    )

    return union_all(override, bridge).subquery("resolved")


def position_ist(db: Session, funding_measure_id: str, org_id: str, position_id: str) -> float:
    resolved = allocation_to_position_subquery(funding_measure_id, org_id)
    total = db.execute(
        select(func.coalesce(func.sum(resolved.c.gewichteter_betrag), 0)).where(
            resolved.c.effective_finanzplan_position_id == position_id
        )
    ).scalar_one()
    return float(total or 0)


def measure_ist_by_position(db: Session, funding_measure_id: str, org_id: str) -> dict[str, float]:
    resolved = allocation_to_position_subquery(funding_measure_id, org_id)
    rows = db.execute(
        select(
            resolved.c.effective_finanzplan_position_id,
            func.coalesce(func.sum(resolved.c.gewichteter_betrag), 0),
        ).group_by(resolved.c.effective_finanzplan_position_id)
    ).all()
    return {pid: float(s or 0) for pid, s in rows}
