"""Tages-Digest — port of app/api/protected/transaktionen/digest.

Last-24h imported transaction count + booking-rule applications grouped by
confidence; ohneRegel = total minus matched.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking_rule import BookingRuleApplication
from app.models.transaction import Transaction


def daily_digest(db: Session, org_id: str) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    total = db.execute(
        select(func.count(Transaction.id)).where(
            Transaction.org_id == org_id, Transaction.created_at >= since
        )
    ).scalar_one()
    rows = db.execute(
        select(BookingRuleApplication.confidence, func.count(BookingRuleApplication.confidence))
        .where(BookingRuleApplication.org_id == org_id, BookingRuleApplication.applied_at >= since)
        .group_by(BookingRuleApplication.confidence)
    ).all()
    by_conf = {c: n for c, n in rows}
    gruen = by_conf.get("GRUEN", 0)
    gelb = by_conf.get("GELB", 0)
    orange = by_conf.get("ORANGE", 0)
    return {
        "total": total,
        "gruen": gruen,
        "gelb": gelb,
        "orange": orange,
        "ohneRegel": total - gruen - gelb - orange,
    }
