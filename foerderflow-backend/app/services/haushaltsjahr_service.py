"""Haushaltsjahre (FiscalYear) — port of app/api/protected/haushaltsjahre/*.

HARD CONSTRAINT: a GESCHLOSSEN year is immutable and cannot be reopened (no
endpoint exists). Closing requires an explicit confirmation token.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import FiscalYearStatus
from app.models.master import FiscalYear
from app.repositories.fiscal_year_repository import FiscalYearRepository

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_date(value: str, code: str, label: str) -> date:
    if not DATE_RE.match(value):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code,
            f"{label} muss ein gültiges Datum im Format YYYY-MM-DD sein.",
        )
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise APIError(  # noqa: B904
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code,
            f"{label} muss ein gültiges Datum im Format YYYY-MM-DD sein.",
        )


def _fy(fy: FiscalYear) -> dict[str, Any]:
    return {
        "id": fy.id,
        "org_id": fy.org_id,
        "jahr": fy.jahr,
        "beginn": fy.beginn.isoformat(),
        "ende": fy.ende.isoformat(),
        "status": fy.status.value,
        "geschlossen_am": fy.geschlossen_am.isoformat() if fy.geschlossen_am else None,
        "geschlossen_von": fy.geschlossen_von,
        "created_at": fy.created_at.isoformat() if fy.created_at else None,
        "updated_at": fy.updated_at.isoformat() if fy.updated_at else None,
    }


class HaushaltsjahrService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FiscalYearRepository(db)

    def list(self, org_id: str) -> list[dict[str, Any]]:
        return [_fy(fy) for fy in self.repo.list_desc(org_id)]

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        fy = self.repo.get(org_id, id_)
        if fy is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Haushaltsjahr nicht gefunden."
            )
        return _fy(fy)

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        jahr = body.get("jahr")
        if not isinstance(jahr, int) or isinstance(jahr, bool) or not (2000 <= jahr <= 2099):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_JAHR",
                "Das Haushaltsjahr muss eine ganze Zahl zwischen 2000 und 2099 sein.",
            )
        beginn_raw, ende_raw = body.get("beginn"), body.get("ende")
        if not isinstance(beginn_raw, str):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_BEGINN",
                "Beginn muss ein gültiges Datum im Format YYYY-MM-DD sein.",
            )
        if not isinstance(ende_raw, str):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_ENDE",
                "Ende muss ein gültiges Datum im Format YYYY-MM-DD sein.",
            )
        beginn = _parse_date(beginn_raw, "VALIDATION_BEGINN", "Beginn")
        ende = _parse_date(ende_raw, "VALIDATION_ENDE", "Ende")
        if beginn >= ende:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_DATES_ORDER",
                "Das Beginndatum muss vor dem Enddatum liegen.",
            )
        if self.repo.get_by_jahr(org_id, jahr):
            raise APIError(
                status.HTTP_409_CONFLICT,
                "JAHR_DUPLICATE",
                f"Das Haushaltsjahr {jahr} existiert für diese Organisation bereits.",
            )
        open_year = self.repo.first_open(org_id)
        fy = FiscalYear(
            org_id=org_id,
            jahr=jahr,
            beginn=beginn,
            ende=ende,
            status=FiscalYearStatus.OFFEN,
        )
        self.repo.add(fy)
        self.db.commit()
        self.db.refresh(fy)
        result: dict[str, Any] = {
            "data": _fy(fy),
            "message": f"Haushaltsjahr {jahr} wurde erfolgreich angelegt.",
        }
        if open_year:
            result["warning"] = (
                f"Achtung: Das Haushaltsjahr {open_year.jahr} ist noch offen. Pro "
                "Organisation sollte nur ein Haushaltsjahr gleichzeitig offen sein."
            )
        return result

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        fy = self.repo.get(org_id, id_)
        if fy is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Haushaltsjahr nicht gefunden."
            )
        if fy.status == FiscalYearStatus.GESCHLOSSEN:
            raise APIError(
                status.HTTP_403_FORBIDDEN,
                "FISCAL_YEAR_CLOSED",
                "Geschlossene Haushaltsjahre können nicht bearbeitet werden.",
            )
        beginn_raw, ende_raw = body.get("beginn"), body.get("ende")
        new_beginn = (
            _parse_date(beginn_raw, "VALIDATION_BEGINN", "Beginn")
            if isinstance(beginn_raw, str)
            else fy.beginn
        )
        new_ende = (
            _parse_date(ende_raw, "VALIDATION_ENDE", "Ende")
            if isinstance(ende_raw, str)
            else fy.ende
        )
        if new_beginn >= new_ende:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_DATES_ORDER",
                "Das Beginndatum muss vor dem Enddatum liegen.",
            )
        if isinstance(beginn_raw, str):
            fy.beginn = new_beginn
        if isinstance(ende_raw, str):
            fy.ende = new_ende
        self.db.commit()
        self.db.refresh(fy)
        return {
            "data": _fy(fy),
            "message": f"Haushaltsjahr {fy.jahr} wurde aktualisiert.",
        }

    def close(
        self, org_id: str, id_: str, body: dict[str, Any], user_id: str | None
    ) -> dict[str, Any]:
        if body.get("confirmation") != "SCHLIESSEN":
            raise APIError(
                status.HTTP_400_BAD_REQUEST,
                "CONFIRMATION_REQUIRED",
                'Zur Bestätigung muss im Body { confirmation: "SCHLIESSEN" } '
                "übergeben werden.",
            )
        fy = self.repo.get(org_id, id_)
        if fy is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Haushaltsjahr nicht gefunden."
            )
        if fy.status == FiscalYearStatus.GESCHLOSSEN:
            raise APIError(
                status.HTTP_409_CONFLICT,
                "ALREADY_CLOSED",
                f"Das Haushaltsjahr {fy.jahr} ist bereits geschlossen.",
            )
        if not user_id:
            raise APIError(
                status.HTTP_401_UNAUTHORIZED,
                "NO_USER_ID",
                "Benutzer-ID konnte nicht ermittelt werden.",
            )
        fy.status = FiscalYearStatus.GESCHLOSSEN
        fy.geschlossen_am = datetime.now(timezone.utc)
        fy.geschlossen_von = user_id
        self.db.commit()
        self.db.refresh(fy)
        return {
            "data": _fy(fy),
            "message": f"Das Haushaltsjahr {fy.jahr} wurde geschlossen. Keine "
            "weiteren Buchungen möglich.",
        }
