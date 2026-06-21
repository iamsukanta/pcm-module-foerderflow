"""Belege (TransactionBeleg) — port of
app/api/protected/transaktionen/[id]/belege(/[belegId]).

Upload (PDF/JPEG/PNG/WEBP, ≤10 MB) to disk OR external reference; retention
(1–10y, default 10); list omits datei_pfad (security); download streams the file
or returns the external ref; DELETE is soft (geloescht_am) with a retention
warning. Files are stored under UPLOAD_DIR/belege/<org>/<tx>/<uuid><ext>.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import APIError
from app.models.transaction import Transaction, TransactionBeleg
from app.services.audit_service import log_audit

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}

UPLOAD_ROOT = Path(getattr(settings, "upload_dir", "") or os.getenv("UPLOAD_DIR", "uploads"))


def _d(v) -> str | None:
    if v is None:
        return None
    return v.isoformat()


def _beleg_public(b: TransactionBeleg) -> dict[str, Any]:
    """List/create shape — datei_pfad intentionally omitted (security)."""
    return {
        "id": b.id,
        "datei_name": b.datei_name,
        "datei_typ": b.datei_typ,
        "externe_referenz": b.externe_referenz,
        "retention_until": _d(b.retention_until),
        "created_at": _d(b.created_at),
    }


class BelegService:
    def __init__(self, db: Session):
        self.db = db

    def _tx(self, org_id: str, tx_id: str) -> Transaction:
        tx = self.db.execute(
            select(Transaction).where(Transaction.id == tx_id, Transaction.org_id == org_id)
        ).scalar_one_or_none()
        if tx is None:
            raise APIError(404, "NOT_FOUND", "Transaktion nicht gefunden")
        return tx

    def list(self, org_id: str, tx_id: str) -> list[dict[str, Any]]:
        self._tx(org_id, tx_id)
        belege = (
            self.db.execute(
                select(TransactionBeleg)
                .where(
                    TransactionBeleg.transaction_id == tx_id,
                    TransactionBeleg.org_id == org_id,
                    TransactionBeleg.geloescht_am.is_(None),
                )
                .order_by(TransactionBeleg.created_at.desc())
            )
            .scalars()
            .all()
        )
        return [_beleg_public(b) for b in belege]

    def _retention_until(self, retention_years: Any) -> date:
        years = 10
        if retention_years not in (None, ""):
            try:
                years = min(10, max(1, int(retention_years)))
            except (TypeError, ValueError):
                years = 10
        today = date.today()
        try:
            return today.replace(year=today.year + years)
        except ValueError:  # Feb 29
            return today.replace(year=today.year + years, day=28)

    def create_external(
        self, org_id: str, user_id: str | None, tx_id: str, externe_referenz: str, retention_years: Any
    ) -> dict[str, Any]:
        self._tx(org_id, tx_id)
        beleg = TransactionBeleg(
            org_id=org_id,
            transaction_id=tx_id,
            externe_referenz=externe_referenz,
            retention_until=self._retention_until(retention_years),
        )
        self.db.add(beleg)
        self.db.commit()
        self.db.refresh(beleg)
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="BELEG_CREATE",
            entitaet="TransactionBeleg",
            entitaet_id=beleg.id,
            nachher={"transaction_id": tx_id, "externe_referenz": beleg.externe_referenz},
        )
        return _beleg_public(beleg)

    def create_upload(
        self,
        org_id: str,
        user_id: str | None,
        tx_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        retention_years: Any,
    ) -> dict[str, Any]:
        self._tx(org_id, tx_id)
        if content_type not in ALLOWED_TYPES:
            raise APIError(
                400,
                "VALIDATION_ERROR",
                "Nicht erlaubter Dateityp. Erlaubt: PDF, JPEG, PNG, WEBP",
            )
        if len(content) > MAX_FILE_SIZE:
            raise APIError(400, "VALIDATION_ERROR", "Datei zu groß. Maximum: 10 MB")

        ext = Path(filename).suffix.lower() or ".bin"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        upload_dir = UPLOAD_ROOT / "belege" / org_id / tx_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / safe_name
        file_path.write_bytes(content)

        beleg = TransactionBeleg(
            org_id=org_id,
            transaction_id=tx_id,
            datei_pfad=str(file_path),
            datei_name=filename,
            datei_typ=content_type,
            retention_until=self._retention_until(retention_years),
        )
        self.db.add(beleg)
        self.db.commit()
        self.db.refresh(beleg)
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="BELEG_CREATE",
            entitaet="TransactionBeleg",
            entitaet_id=beleg.id,
            nachher={"transaction_id": tx_id, "datei_name": beleg.datei_name, "datei_typ": beleg.datei_typ},
        )
        return _beleg_public(beleg)

    def get_for_download(self, org_id: str, tx_id: str, beleg_id: str) -> TransactionBeleg:
        beleg = self.db.execute(
            select(TransactionBeleg).where(
                TransactionBeleg.id == beleg_id,
                TransactionBeleg.transaction_id == tx_id,
                TransactionBeleg.org_id == org_id,
                TransactionBeleg.geloescht_am.is_(None),
            )
        ).scalar_one_or_none()
        if beleg is None:
            raise APIError(404, "NOT_FOUND", "Beleg nicht gefunden")
        return beleg

    def soft_delete(self, org_id: str, tx_id: str, beleg_id: str) -> dict[str, Any]:
        beleg = self.db.execute(
            select(TransactionBeleg).where(
                TransactionBeleg.id == beleg_id,
                TransactionBeleg.transaction_id == tx_id,
                TransactionBeleg.org_id == org_id,
                TransactionBeleg.geloescht_am.is_(None),
            )
        ).scalar_one_or_none()
        if beleg is None:
            raise APIError(404, "NOT_FOUND", "Beleg nicht gefunden")
        retention = beleg.retention_until
        beleg.geloescht_am = datetime.now(timezone.utc)
        self.db.commit()
        result: dict[str, Any] = {"data": {"message": "Beleg wurde als gelöscht markiert"}}
        today = date.today()
        if retention > today:
            days_left = (retention - today).days
            tag = "Tag" if days_left == 1 else "Tage"
            result["warning"] = (
                f"Aufbewahrungsfrist läuft noch {days_left} {tag} "
                f"(bis {retention.strftime('%d.%m.%Y')})."
            )
        return result
