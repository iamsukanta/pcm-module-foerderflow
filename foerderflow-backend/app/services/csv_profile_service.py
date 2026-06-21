"""CSV import profiles — port of app/api/protected/csv-profiles.

GET: systemwide + own profiles. POST: create an org-owned profile.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.transaction import CsvImportProfile


def _profile(p: CsvImportProfile) -> dict[str, Any]:
    return {
        "id": p.id,
        "org_id": p.org_id,
        "name": p.name,
        "beschreibung": p.beschreibung,
        "delimiter": p.delimiter,
        "encoding": p.encoding,
        "quote_char": p.quote_char,
        "decimal_separator": p.decimal_separator,
        "thousand_separator": p.thousand_separator,
        "date_format": p.date_format,
        "header_row": p.header_row,
        "skip_rows": p.skip_rows,
        "column_mappings": p.column_mappings,
        "auto_detect_pattern": p.auto_detect_pattern,
        "ist_systemweit": p.ist_systemweit,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


class CsvProfileService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, org_id: str) -> list[dict[str, Any]]:
        profiles = (
            self.db.execute(
                select(CsvImportProfile)
                .where(
                    (CsvImportProfile.ist_systemweit.is_(True))
                    | (CsvImportProfile.org_id == org_id)
                )
                .order_by(CsvImportProfile.ist_systemweit.desc(), CsvImportProfile.name.asc())
            )
            .scalars()
            .all()
        )
        return [_profile(p) for p in profiles]

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        name = str(body.get("name") or "").strip()
        if not name or not (2 <= len(name) <= 120):
            raise APIError(422, "VALIDATION_NAME", "Name muss 2–120 Zeichen lang sein.")
        p = CsvImportProfile(
            org_id=org_id,
            name=name,
            beschreibung=str(body["beschreibung"]) if body.get("beschreibung") else None,
            delimiter=str(body.get("delimiter") or ";"),
            encoding=str(body.get("encoding") or "utf-8"),
            quote_char=str(body.get("quote_char") or '"'),
            decimal_separator=str(body.get("decimal_separator") or ","),
            thousand_separator=str(body["thousand_separator"]) if body.get("thousand_separator") else None,
            date_format=str(body.get("date_format") or "dd.MM.yyyy"),
            header_row=int(body.get("header_row") or 1),
            skip_rows=int(body.get("skip_rows") or 0),
            column_mappings=body.get("column_mappings") or {},
            auto_detect_pattern=str(body["auto_detect_pattern"]) if body.get("auto_detect_pattern") else None,
            ist_systemweit=False,
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return _profile(p)
