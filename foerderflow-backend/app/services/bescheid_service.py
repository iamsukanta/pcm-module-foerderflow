"""Bescheid document (PDF in DB) — port of foerdermassnahmen/[id]/bescheid.

GET streams the PDF inline, POST upserts (PDF ≤10 MB), DELETE removes. WIDERRUFEN
measures block upload/delete.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.funding import BescheidDokument, FundingMeasure

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME = "application/pdf"
VALID_QUELLE = ("OCR_IMPORT", "MANUAL_UPLOAD")


def _ev(v):
    return v.value if hasattr(v, "value") else v


class BescheidService:
    def __init__(self, db: Session):
        self.db = db

    def _measure(self, org_id: str, measure_id: str) -> FundingMeasure:
        m = self.db.execute(
            select(FundingMeasure).where(
                FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none()
        if m is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
        return m

    def get(self, org_id: str, measure_id: str) -> BescheidDokument:
        dok = self.db.execute(
            select(BescheidDokument).where(
                BescheidDokument.funding_measure_id == measure_id,
                BescheidDokument.org_id == org_id,
            )
        ).scalar_one_or_none()
        if dok is None:
            raise APIError(404, "NOT_FOUND", "Kein Zuwendungsbescheid hinterlegt.")
        return dok

    def ensure_uploadable(self, org_id: str, measure_id: str) -> FundingMeasure:
        m = self._measure(org_id, measure_id)
        if _ev(m.status) == "WIDERRUFEN":
            raise APIError(409, "MEASURE_REVOKED", "Massnahme ist widerrufen — Upload nicht möglich.")
        return m

    def upsert(
        self, org_id: str, measure_id: str, filename: str, content_type: str, content: bytes, quelle_raw: str | None
    ) -> dict[str, Any]:
        if content_type != ALLOWED_MIME:
            raise APIError(400, "INVALID_FILE_TYPE", "Nur PDF-Dateien werden unterstützt.")
        if len(content) > MAX_FILE_SIZE:
            raise APIError(400, "FILE_TOO_LARGE", "Datei ist zu groß (max. 10 MB).")
        if len(content) == 0:
            raise APIError(400, "FILE_EMPTY", "Datei ist leer.")
        quelle = quelle_raw if quelle_raw in VALID_QUELLE else "MANUAL_UPLOAD"
        existing = self.db.execute(
            select(BescheidDokument).where(BescheidDokument.funding_measure_id == measure_id)
        ).scalar_one_or_none()
        if existing:
            existing.filename = filename[:255]
            existing.mime_type = ALLOWED_MIME
            existing.size_bytes = len(content)
            existing.bytes = content
            existing.quelle = quelle
            existing.uploaded_at = datetime.now(timezone.utc)
            dok = existing
        else:
            dok = BescheidDokument(
                org_id=org_id,
                funding_measure_id=measure_id,
                filename=filename[:255],
                mime_type=ALLOWED_MIME,
                size_bytes=len(content),
                bytes=content,
                quelle=quelle,
            )
            self.db.add(dok)
        self.db.commit()
        self.db.refresh(dok)
        return {
            "data": {
                "id": dok.id,
                "filename": dok.filename,
                "mime_type": dok.mime_type,
                "size_bytes": dok.size_bytes,
                "uploaded_at": dok.uploaded_at.isoformat() if dok.uploaded_at else None,
                "quelle": _ev(dok.quelle),
            }
        }

    def delete(self, org_id: str, measure_id: str) -> dict[str, Any]:
        m = self._measure(org_id, measure_id)
        if _ev(m.status) == "WIDERRUFEN":
            raise APIError(409, "MEASURE_REVOKED", "Massnahme ist widerrufen — Löschen nicht möglich.")
        dok = self.db.execute(
            select(BescheidDokument).where(
                BescheidDokument.funding_measure_id == measure_id,
                BescheidDokument.org_id == org_id,
            )
        ).scalar_one_or_none()
        if dok is None:
            raise APIError(404, "NOT_FOUND", "Kein Zuwendungsbescheid hinterlegt.")
        dok_id = dok.id
        self.db.delete(dok)
        self.db.commit()
        return {"data": {"id": dok_id}}
