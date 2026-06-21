"""confirm_transaction — port of lib/transaktion-confirm.ts.

Raises the last-applied BookingRule's match_count, recomputes confidence
(ORANGE→GELB→GRÜN), updates the application's confidence, and sets the
transaction status to KATEGORISIERT. Returns ok/reason (never raises) so batch
callers can collect per-item failures.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.booking_rule import BookingRuleApplication
from app.models.transaction import Transaction
from app.services.booking_rules import calculate_confidence


@dataclass
class ConfirmResult:
    ok: bool
    id: str
    reason: str | None = None


def confirm_transaction(db: Session, org_id: str, transaction_id: str) -> ConfirmResult:
    tx = db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.org_id == org_id)
        .options(
            selectinload(Transaction.rule_applications).selectinload(
                BookingRuleApplication.rule
            )
        )
    ).scalar_one_or_none()
    if tx is None:
        return ConfirmResult(False, transaction_id, "Transaktion nicht gefunden.")

    apps = sorted(tx.rule_applications, key=lambda a: a.applied_at, reverse=True)
    last = apps[0] if apps else None
    if last is not None:
        new_count = last.rule.match_count + 1
        new_conf = calculate_confidence(new_count)
        last.rule.match_count = new_count
        last.rule.confidence = new_conf
        last.confidence = new_conf

    tx.status = "KATEGORISIERT"
    db.commit()
    return ConfirmResult(True, transaction_id)
