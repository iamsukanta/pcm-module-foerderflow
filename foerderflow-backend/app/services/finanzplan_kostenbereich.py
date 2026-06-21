"""resolve_kostenbereiche — port of lib/finanzplan-positionen.ts.

Validates a kostenbereiche array and resolves `kostenbereich_code` → id (accepts
either `kostenbereich_id` or `kostenbereich_code`). Raises APIError on invalid input
(the monolith returns the same {error, code} envelope).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.master import Kostenbereich


@dataclass
class ResolvedKostenbereich:
    kostenbereich_id: str
    foerderfahig_anteil: float
    cap_betrag: float | None
    hinweis: str | None


def resolve_kostenbereiche(db: Session, raw: Any) -> list[ResolvedKostenbereich]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise APIError(422, "VALIDATION_KOSTENBEREICHE", "kostenbereiche muss ein Array sein.")

    codes: set[str] = set()
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("kostenbereich_id"), str):
            continue
        if (
            isinstance(item, dict)
            and isinstance(item.get("kostenbereich_code"), str)
            and item["kostenbereich_code"].strip()
        ):
            codes.add(item["kostenbereich_code"].strip())
        else:
            raise APIError(
                422,
                "VALIDATION_KOSTENBEREICH_KEY",
                "Jeder Kostenbereich braucht entweder kostenbereich_id oder kostenbereich_code.",
            )

    code_to_id: dict[str, str] = {}
    if codes:
        found = db.execute(
            select(Kostenbereich.id, Kostenbereich.code).where(
                Kostenbereich.code.in_(list(codes))
            )
        ).all()
        code_to_id = {code: kid for kid, code in found}
        missing = [c for c in codes if c not in code_to_id]
        if missing:
            raise APIError(
                422,
                "VALIDATION_KOSTENBEREICH_CODE",
                f"Unbekannte Kostenbereich-Codes: {', '.join(missing)}",
            )

    seen: set[str] = set()
    entries: list[ResolvedKostenbereich] = []
    for item in raw:
        kid = (
            item["kostenbereich_id"]
            if isinstance(item.get("kostenbereich_id"), str)
            else code_to_id[str(item["kostenbereich_code"]).strip()]
        )
        if kid in seen:
            continue
        seen.add(kid)

        anteil = item["foerderfahig_anteil"] if isinstance(item.get("foerderfahig_anteil"), (int, float)) and not isinstance(item.get("foerderfahig_anteil"), bool) else 1
        if anteil < 0 or anteil > 1:
            raise APIError(
                422,
                "VALIDATION_ANTEIL",
                f"foerderfahig_anteil muss zwischen 0 und 1 liegen (Wert: {anteil}).",
            )
        cap_raw = item.get("cap_betrag")
        cap = cap_raw if isinstance(cap_raw, (int, float)) and not isinstance(cap_raw, bool) and cap_raw > 0 else None
        hinweis = item["hinweis"].strip() if isinstance(item.get("hinweis"), str) and item["hinweis"].strip() else None
        entries.append(
            ResolvedKostenbereich(
                kostenbereich_id=kid,
                foerderfahig_anteil=float(anteil),
                cap_betrag=float(cap) if cap is not None else None,
                hinweis=hinweis,
            )
        )
    return entries
