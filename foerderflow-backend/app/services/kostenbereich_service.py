"""Kostenbereiche (cost-category taxonomy) — port of
app/api/protected/kostenbereiche (read-only for org users).

Parity note: the monolith query applies NO org filter (returns the systemwide
taxonomy plus any org sub-categories). Reproduced exactly. `nur_obergruppen=true`
returns only top-level (parent_id IS NULL) entries; each includes `kinder`
ordered by sort_order.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.master import Kostenbereich


def _kb(kb: Kostenbereich, with_kinder: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": kb.id,
        "code": kb.code,
        "bezeichnung": kb.bezeichnung,
        "beschreibung": kb.beschreibung,
        "parent_id": kb.parent_id,
        "org_id": kb.org_id,
        "ist_aktiv": kb.ist_aktiv,
        "skr42_konto_von": kb.skr42_konto_von,
        "skr42_konto_bis": kb.skr42_konto_bis,
        "ist_personal": kb.ist_personal,
        "ist_gemeinkosten": kb.ist_gemeinkosten,
        "belegpflicht_default": kb.belegpflicht_default,
        "foerderfahig_default": kb.foerderfahig_default,
        "sort_order": kb.sort_order,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    }
    if with_kinder:
        kinder = sorted(kb.kinder, key=lambda c: c.sort_order)
        row["kinder"] = [_kb(c, with_kinder=False) for c in kinder]
    return row


class KostenbereichService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, nur_obergruppen: bool) -> list[dict[str, Any]]:
        stmt = (
            select(Kostenbereich)
            .options(selectinload(Kostenbereich.kinder))
            .order_by(Kostenbereich.sort_order.asc())
        )
        if nur_obergruppen:
            stmt = stmt.where(Kostenbereich.parent_id.is_(None))
        items = self.db.execute(stmt).scalars().all()
        return [_kb(kb) for kb in items]
