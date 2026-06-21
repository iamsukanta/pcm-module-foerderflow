"""Duplicate detection — port of lib/import/duplicate.ts."""

from __future__ import annotations

import hashlib
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction


def create_duplikat_hash(datum: date, betrag: float, auftraggeber: str | None) -> str:
    s = f"{datum.isoformat()}|{betrag:.2f}|{auftraggeber or ''}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def find_duplicates(db: Session, org_id: str, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    rows = db.execute(
        select(Transaction.duplikat_hash).where(
            Transaction.org_id == org_id, Transaction.duplikat_hash.in_(hashes)
        )
    ).all()
    return {r[0] for r in rows if r[0] is not None}
