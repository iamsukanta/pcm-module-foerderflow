"""Durchführungszeitraum validation — port of lib/foerdermassnahme-zeitraum.ts.

Rules: both Durchführung dates set or both empty; von < bis; must lie within the
Bewilligungszeitraum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class ZeitraumResult:
    ok: bool
    durchfuehrungs_von: date | None = None
    durchfuehrungs_bis: date | None = None
    code: str | None = None
    message: str | None = None


def _to_date(v: str | date | None) -> date | None:
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


def _is_clear(v: str | date | None) -> bool:
    return v is None or v == ""


def validate_durchfuehrungszeitraum(
    bewilligungs_von: date,
    bewilligungs_bis: date,
    durchfuehrungs_von: str | date | None,
    durchfuehrungs_bis: str | date | None,
) -> ZeitraumResult:
    von_clear = _is_clear(durchfuehrungs_von)
    bis_clear = _is_clear(durchfuehrungs_bis)

    if von_clear and bis_clear:
        return ZeitraumResult(ok=True, durchfuehrungs_von=None, durchfuehrungs_bis=None)

    if von_clear != bis_clear:
        return ZeitraumResult(
            ok=False,
            code="VALIDATION_DURCHFUEHRUNG_PARTIAL",
            message="Durchführungszeitraum: bitte beide Daten angeben oder beide leer lassen.",
        )

    von = _to_date(durchfuehrungs_von)
    bis = _to_date(durchfuehrungs_bis)

    if von is None:
        return ZeitraumResult(
            ok=False,
            code="VALIDATION_DURCHFUEHRUNG_VON",
            message="Durchführung von ist kein gültiges Datum.",
        )
    if bis is None:
        return ZeitraumResult(
            ok=False,
            code="VALIDATION_DURCHFUEHRUNG_BIS",
            message="Durchführung bis ist kein gültiges Datum.",
        )
    if von >= bis:
        return ZeitraumResult(
            ok=False,
            code="VALIDATION_DURCHFUEHRUNG_RANGE",
            message="Durchführungszeitraum: Beginn muss vor Ende liegen.",
        )
    if von < bewilligungs_von or bis > bewilligungs_bis:
        return ZeitraumResult(
            ok=False,
            code="VALIDATION_DURCHFUEHRUNG_OUTSIDE_BEWILLIGUNG",
            message="Durchführungszeitraum muss innerhalb des Bewilligungszeitraums liegen.",
        )
    return ZeitraumResult(ok=True, durchfuehrungs_von=von, durchfuehrungs_bis=bis)
