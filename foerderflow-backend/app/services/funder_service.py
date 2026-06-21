"""Funder (Fördergeber) business logic — port of app/api/protected/funder/*.

Parity note: the create/update API only accepts 5 of the 7 FunderTyp values
(KIRCHE and PRIVAT exist in the DB enum but are NOT accepted by these endpoints).
DELETE is a hard delete, allowed only when no funding measures are linked.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.master import Funder
from app.repositories.funder_repository import FunderRepository

VALID_FUNDER_TYPEN = ("STIFTUNG", "KOMMUNE", "MINISTERIUM", "EU", "ANDERE")


from app.utils.serialization import decimal_str as _dec  # noqa: E402


def _funder(f: Funder, count: int) -> dict[str, Any]:
    return {
        "id": f.id,
        "org_id": f.org_id,
        "name": f.name,
        "typ": f.typ.value,
        "notizen": f.notizen,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        "_count": {"funding_measures": count},
    }


class FunderService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FunderRepository(db)

    def list(self, org_id: str) -> list[dict[str, Any]]:
        funders = self.repo.list_ordered(org_id)
        counts = self.repo.measure_counts([f.id for f in funders])
        return [_funder(f, counts.get(f.id, 0)) for f in funders]

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        f = self.repo.get_with_measures(org_id, id_)
        if f is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Fördergeber nicht gefunden."
            )
        row = _funder(f, len(f.funding_measures))
        measures = sorted(f.funding_measures, key=lambda m: m.created_at, reverse=True)
        row["funding_measures"] = [
            {
                "id": m.id,
                "name": m.name,
                "status": m.status.value,
                "budget_gesamt": _dec(m.budget_gesamt),
                "foerderquote": _dec(m.foerderquote),
                "laufzeit_von": m.laufzeit_von.isoformat(),
                "laufzeit_bis": m.laufzeit_bis.isoformat(),
            }
            for m in measures
        ]
        return row

    def _validate_name(self, name: Any) -> str:
        if not isinstance(name, str) or not (2 <= len(name.strip()) <= 200):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_NAME",
                "Name muss zwischen 2 und 200 Zeichen lang sein.",
            )
        return name.strip()

    def _validate_typ(self, typ: Any) -> str:
        if typ not in VALID_FUNDER_TYPEN:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_TYP",
                f"Ungültiger Fördergeber-Typ. Erlaubt: {', '.join(VALID_FUNDER_TYPEN)}.",
            )
        return typ

    def _validate_notizen(self, notizen: Any) -> str | None:
        if notizen is None:
            return None
        if not isinstance(notizen, str):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_NOTIZEN",
                "Notizen müssen ein Text sein.",
            )
        return notizen.strip() or None

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        name = self._validate_name(body.get("name"))
        typ = self._validate_typ(body.get("typ"))
        notizen = (
            self._validate_notizen(body.get("notizen"))
            if "notizen" in body
            else None
        )
        f = Funder(org_id=org_id, name=name, typ=typ, notizen=notizen)
        self.repo.add(f)
        self.db.commit()
        self.db.refresh(f)
        return _funder(f, 0)

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        f = self.repo.get(org_id, id_)
        if f is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Fördergeber nicht gefunden."
            )
        if "name" in body:
            f.name = self._validate_name(body["name"])
        if "typ" in body:
            f.typ = self._validate_typ(body["typ"])
        if "notizen" in body:
            f.notizen = self._validate_notizen(body["notizen"])
        self.db.commit()
        self.db.refresh(f)
        return _funder(f, self.repo.measure_count(f.id))

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        f = self.repo.get(org_id, id_)
        if f is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Fördergeber nicht gefunden."
            )
        count = self.repo.measure_count(f.id)
        if count > 0:
            raise APIError(
                status.HTTP_409_CONFLICT,
                "HAS_MEASURES",
                f'Fördergeber „{f.name}" kann nicht gelöscht werden, da noch {count} '
                "Fördermassnahme(n) verknüpft sind. Bitte erst alle Massnahmen "
                "entfernen oder widerrufen.",
            )
        name = f.name
        self.db.delete(f)
        self.db.commit()
        return {"data": None, "message": f'Fördergeber „{name}" wurde gelöscht.'}
