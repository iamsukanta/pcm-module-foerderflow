"""Booking-rule engine — port of lib/booking-rules.ts.

- calculate_confidence: ORANGE/GELB/GRÜN by match_count.
- build_rule_match_conditions: SQLAlchemy port of buildRuleMatchWhere (single
  source of truth for preview + backfill; betrag range on |betrag|).
- apply_rule_to_transaction: applies a rule (set_kostenbereich override, replace
  splits with rounding correction, raise match_count/confidence, audit
  application, auto FundAllocation per split, status transitions).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.booking_rule import BookingRule, BookingRuleApplication
from app.models.funding import FundingMeasure
from app.models.transaction import FundAllocation, Transaction, TransactionSplit
from app.services.allocation_betraege import _round2, compute_allocation_betraege


def calculate_confidence(match_count: int) -> str:
    if match_count >= 5:
        return "GRUEN"
    if match_count >= 2:
        return "GELB"
    return "ORANGE"


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n else None


def _to_date(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(v)[:10])
        except ValueError:
            return None


def build_rule_match_conditions(org_id: str, match: dict[str, Any]) -> list:
    conds = [Transaction.org_id == org_id]
    ma = match.get("match_auftraggeber")
    if ma:
        if match.get("match_auftraggeber_exact"):
            conds.append(func.lower(Transaction.auftraggeber) == ma.lower())
        else:
            conds.append(func.lower(Transaction.auftraggeber).like(f"%{ma.lower()}%"))
    mv = match.get("match_verwendungszweck")
    if mv:
        conds.append(func.lower(Transaction.verwendungszweck).like(f"%{mv.lower()}%"))
    if match.get("match_kostenbereich_id"):
        conds.append(Transaction.kostenbereich_id == match["match_kostenbereich_id"])
    if match.get("match_iban_partner"):
        conds.append(Transaction.iban_partner == match["match_iban_partner"])

    bmin = _num(match.get("match_betrag_min"))
    bmax = _num(match.get("match_betrag_max"))
    if bmin is not None or bmax is not None:
        pos = []
        neg = []
        if bmin is not None:
            pos.append(Transaction.betrag >= bmin)
            neg.append(Transaction.betrag <= -bmin)
        if bmax is not None:
            pos.append(Transaction.betrag <= bmax)
            neg.append(Transaction.betrag >= -bmax)
        conds.append(or_(and_(*pos), and_(*neg)))

    dvon = _to_date(match.get("match_datum_von"))
    dbis = _to_date(match.get("match_datum_bis"))
    if dvon:
        conds.append(Transaction.datum >= dvon)
    if dbis:
        conds.append(Transaction.datum <= dbis)
    return conds


def apply_rule_to_transaction(
    db: Session,
    org_id: str,
    transaction_id: str,
    betrag: float,
    rule: BookingRule,
    applied_by: str | None = None,
) -> None:
    """Apply `rule` (with splits loaded) to a transaction. Commits on success;
    on error the caller rolls back and counts it as skipped."""
    if rule.set_kostenbereich_id:
        tx0 = db.get(Transaction, transaction_id)
        if tx0 is not None:
            tx0.kostenbereich_id = rule.set_kostenbereich_id

    existing = (
        db.execute(
            select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
        )
        .scalars()
        .all()
    )
    for s in existing:
        db.delete(s)
    db.flush()

    rule_splits = sorted(rule.splits, key=lambda s: s.id)
    split_betraege: list[float] = []
    running = 0.0
    n = len(rule_splits)
    for i in range(n - 1):
        b = _round2(betrag * float(rule_splits[i].prozent) / 100)
        split_betraege.append(b)
        running += b
    if n > 0:
        split_betraege.append(_round2(betrag - running))

    created: list[tuple[TransactionSplit, Any]] = []
    for rs, b in zip(rule_splits, split_betraege):
        ts = TransactionSplit(
            org_id=org_id,
            transaction_id=transaction_id,
            cost_center_id=rs.cost_center_id,
            prozent=float(rs.prozent),
            betrag_anteil=b,
            allocation_key_id=rs.allocation_key_id,
        )
        db.add(ts)
        db.flush()
        created.append((ts, rs))

    new_count = rule.match_count + 1
    new_conf = calculate_confidence(new_count)
    rule.match_count = new_count
    rule.confidence = new_conf

    db.add(
        BookingRuleApplication(
            org_id=org_id,
            transaction_id=transaction_id,
            rule_id=rule.id,
            applied_by=applied_by,
            confidence=new_conf,
        )
    )

    tx = db.get(Transaction, transaction_id)
    if tx is not None and (tx.status.value if hasattr(tx.status, "value") else tx.status) == "IMPORTIERT":
        tx.status = "KATEGORISIERT"

    measure_cache: dict[str, dict[str, Any] | None] = {}

    def _measure_ctx(measure_id: str):
        if measure_id in measure_cache:
            return measure_cache[measure_id]
        m = db.execute(
            select(FundingMeasure).where(FundingMeasure.id == measure_id)
        ).scalar_one_or_none()
        ctx = (
            None
            if m is None
            else {
                "foerderquote": float(m.foerderquote),
                "mwst_foerderfahig": m.mwst_foerderfahig,
                "mwst_satz": float(m.mwst_satz_prozent),
            }
        )
        measure_cache[measure_id] = ctx
        return ctx

    any_allocated = False
    for ts, rs in created:
        measure_id = rs.funding_measure_id or rule.funding_measure_id
        if not measure_id:
            continue
        ctx = _measure_ctx(measure_id)
        if ctx is None:
            continue
        alloc_prozent = float(rs.allocation_prozent) if rs.allocation_prozent is not None else 100
        b = compute_allocation_betraege(
            abs(float(ts.betrag_anteil)),
            ctx["foerderquote"],
            ctx["mwst_foerderfahig"],
            ctx["mwst_satz"],
        )
        db.add(
            FundAllocation(
                org_id=org_id,
                transaction_split_id=ts.id,
                funding_measure_id=measure_id,
                prozent=alloc_prozent,
                betrag_foerderfahig=b.betrag_foerderfahig,
                betrag_foerderung=b.betrag_foerderung,
                betrag_eigenanteil=b.betrag_eigenanteil,
                status="VORLAEUFIG",
            )
        )
        any_allocated = True

    if any_allocated and tx is not None:
        tx.status = "ZUGEORDNET"

    db.commit()


def load_rule_with_splits(db: Session, org_id: str, rule_id: str, active_only: bool = False) -> BookingRule | None:
    stmt = select(BookingRule).where(BookingRule.id == rule_id, BookingRule.org_id == org_id)
    if active_only:
        stmt = stmt.where(BookingRule.aktiv.is_(True))
    return db.execute(stmt.options(selectinload(BookingRule.splits))).scalar_one_or_none()
