"""Small request-body validation helpers shared across PCM controllers.

They raise the project's ``APIError`` envelope (422) with stable codes, matching
the validation style of the existing services.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.errors import APIError


def parse_date(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise APIError(422, "VALIDATION_DATE", f"{field} muss ein Datum (YYYY-MM-DD) sein.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise APIError(  # noqa: B904
            422, "VALIDATION_DATE", f"{field} ist kein gültiges Datum (YYYY-MM-DD)."
        )


def opt_date(value: Any, field: str) -> date | None:
    return None if value is None else parse_date(value, field)


def req_str(body: dict[str, Any], field: str) -> str:
    v = body.get(field)
    if not isinstance(v, str) or not v.strip():
        raise APIError(422, "VALIDATION_REQUIRED", f"{field} ist erforderlich.")
    return v.strip()


def req_int(body: dict[str, Any], field: str) -> int:
    v = body.get(field)
    if isinstance(v, bool):
        raise APIError(422, "VALIDATION_INT", f"{field} muss eine ganze Zahl sein.")
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    raise APIError(422, "VALIDATION_INT", f"{field} muss eine ganze Zahl sein.")


def req_num(body: dict[str, Any], field: str) -> float:
    v = body.get(field)
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise APIError(422, "VALIDATION_NUMBER", f"{field} muss eine Zahl sein.")
    return float(v)


def opt_num(body: dict[str, Any], field: str) -> float | None:
    v = body.get(field)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise APIError(422, "VALIDATION_NUMBER", f"{field} muss eine Zahl sein.")
    return float(v)
