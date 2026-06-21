"""Verteilungsschlüssel (AllocationKey) — port of
app/api/protected/verteilungsschluessel/*.

INVARIANT: Σ position.prozent per key == exactly 100.000 (else 400
INVARIANT_SUM_NOT_100). Editing name/gueltig_bis is in-place; changing basis or
positions creates a new version (neue-version) which closes the prior key
(gueltig_bis = neue_von − 1 day, ist_aktiv=false) and chains parent_key_id to the
family root. prozent serializes as string; dates as YYYY-MM-DD.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.allocation import AllocationKey, AllocationKeyPosition
from app.models.master import CostCenter
from app.utils.serialization import decimal_str

VALID_BASES = ("MITARBEITERZAHL", "QUADRATMETER", "BUDGET_ANTEIL", "MANUELL")
_FAR_FUTURE = date(9999, 12, 31)


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _parse_date(v: Any) -> date | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None


def sum_prozent(values: list[Any]) -> float:
    return round(sum(_num(v) for v in values), 3)


def is_exact_100(s: float) -> bool:
    return abs(s - 100) < 0.001


def _overlaps(a_von: date, a_bis: date | None, b_von: date, b_bis: date | None) -> bool:
    a_end = a_bis or _FAR_FUTURE
    b_end = b_bis or _FAR_FUTURE
    return a_von <= b_end and b_von <= a_end


def _key_scalars(k: AllocationKey) -> dict[str, Any]:
    return {
        "id": k.id,
        "org_id": k.org_id,
        "name": k.name,
        "basis": _ev(k.basis),
        "gueltig_von": k.gueltig_von.isoformat(),
        "gueltig_bis": k.gueltig_bis.isoformat() if k.gueltig_bis else None,
        "ist_aktiv": k.ist_aktiv,
        "parent_key_id": k.parent_key_id,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


def _position(p: AllocationKeyPosition) -> dict[str, Any]:
    cc = p.cost_center
    return {
        "id": p.id,
        "org_id": p.org_id,
        "allocation_key_id": p.allocation_key_id,
        "cost_center_id": p.cost_center_id,
        "prozent": decimal_str(p.prozent),
        "cost_center": {"id": cc.id, "name": cc.name, "code": cc.code, "typ": _ev(cc.typ)},
    }


class VerteilungsschluesselService:
    def __init__(self, db: Session):
        self.db = db

    def _get(self, org_id: str, id_: str) -> AllocationKey | None:
        return self.db.execute(
            select(AllocationKey).where(
                AllocationKey.id == id_, AllocationKey.org_id == org_id
            )
        ).scalar_one_or_none()

    def _with_positions(self, org_id: str, id_: str) -> AllocationKey | None:
        return self.db.execute(
            select(AllocationKey)
            .where(AllocationKey.id == id_, AllocationKey.org_id == org_id)
            .options(
                selectinload(AllocationKey.positions).selectinload(
                    AllocationKeyPosition.cost_center
                )
            )
        ).scalar_one_or_none()

    def _enrich(self, k: AllocationKey) -> dict[str, Any]:
        positions = sorted(k.positions, key=lambda p: p.cost_center.code)
        pos_ser = [_position(p) for p in positions]
        summe = sum_prozent([p["prozent"] for p in pos_ser])
        row = _key_scalars(k)
        row["positions"] = pos_ser
        row["summe_prozent"] = summe
        row["is_valid"] = is_exact_100(summe)
        return row

    # ── list / get ────────────────────────────────────────────────────────────
    def list(self, org_id: str, include_inactive: bool) -> list[dict[str, Any]]:
        stmt = (
            select(AllocationKey)
            .where(AllocationKey.org_id == org_id)
            .options(
                selectinload(AllocationKey.positions).selectinload(
                    AllocationKeyPosition.cost_center
                )
            )
            .order_by(AllocationKey.ist_aktiv.desc(), AllocationKey.gueltig_von.desc())
        )
        if not include_inactive:
            stmt = stmt.where(AllocationKey.ist_aktiv.is_(True))
        return [self._enrich(k) for k in self.db.execute(stmt).scalars().all()]

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        k = self._with_positions(org_id, id_)
        if k is None:
            raise APIError(404, "NOT_FOUND", "Verteilungsschlüssel nicht gefunden.")
        return self._enrich(k)

    # ── shared position validation ────────────────────────────────────────────
    def _validate_positions(self, org_id: str, positions: Any) -> list[dict[str, Any]]:
        if not isinstance(positions, list) or len(positions) == 0:
            raise APIError(
                422,
                "VALIDATION_POSITIONS_EMPTY",
                "Mindestens eine Position (Kostenstelle + Anteil) ist erforderlich.",
            )
        cc_ids = [p.get("cost_center_id") for p in positions]
        if len(set(cc_ids)) != len(cc_ids):
            raise APIError(
                422,
                "VALIDATION_POSITIONS_DUPLICATE",
                "Jede Kostenstelle darf nur einmal pro Schlüssel vorkommen.",
            )
        for pos in positions:
            p = _num(pos.get("prozent"))
            if p != p or p <= 0 or p > 100:  # NaN check via p!=p
                raise APIError(
                    422,
                    "VALIDATION_PROZENT_RANGE",
                    "Alle Prozentwerte müssen zwischen 0.001 und 100 liegen.",
                )
        summe = sum_prozent([p.get("prozent") for p in positions])
        if not is_exact_100(summe):
            raise APIError(
                400,
                "INVARIANT_SUM_NOT_100",
                f"Die Summe der Prozentwerte muss exakt 100,00 % ergeben. "
                f"Aktuell: {summe:.2f} %.",
                extra={"summe_prozent": summe},
            )
        valid = self.db.execute(
            select(CostCenter.id).where(
                CostCenter.id.in_([c for c in cc_ids if isinstance(c, str)]),
                CostCenter.org_id == org_id,
                CostCenter.ist_aktiv.is_(True),
            )
        ).all()
        if len({r[0] for r in valid}) != len(set(cc_ids)):
            raise APIError(
                422,
                "COST_CENTER_INVALID",
                "Eine oder mehrere Kostenstellen wurden nicht gefunden oder sind inaktiv.",
            )
        return positions

    # ── create ────────────────────────────────────────────────────────────────
    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        name = body.get("name")
        if not isinstance(name, str) or not (2 <= len(name.strip()) <= 100):
            raise APIError(422, "VALIDATION_NAME", "Name muss zwischen 2 und 100 Zeichen lang sein.")
        basis = body.get("basis")
        if basis not in VALID_BASES:
            raise APIError(
                422, "VALIDATION_BASIS", f"Ungültige Basis. Erlaubt: {', '.join(VALID_BASES)}."
            )
        gv = body.get("gueltig_von")
        if not isinstance(gv, str) or not gv:
            raise APIError(422, "VALIDATION_GUELTIG_VON", "Gültig-von-Datum ist erforderlich.")
        von = _parse_date(gv)
        if von is None:
            raise APIError(422, "VALIDATION_GUELTIG_VON", "Ungültiges Gültig-von-Datum.")
        gb = body.get("gueltig_bis")
        bis: date | None = None
        if gb not in (None, ""):
            if not isinstance(gb, str):
                raise APIError(422, "VALIDATION_GUELTIG_BIS", "Ungültiges Gültig-bis-Datum.")
            bis = _parse_date(gb)
            if bis is None:
                raise APIError(422, "VALIDATION_GUELTIG_BIS", "Ungültiges Gültig-bis-Datum.")
            if bis <= von:
                raise APIError(422, "VALIDATION_DATE_ORDER", "Gültig-bis muss nach Gültig-von liegen.")

        positions = self._validate_positions(org_id, body.get("positions"))

        warnings: list[str] = []
        for ak in self.db.execute(
            select(AllocationKey).where(
                AllocationKey.org_id == org_id, AllocationKey.ist_aktiv.is_(True)
            )
        ).scalars().all():
            if _overlaps(von, bis, ak.gueltig_von, ak.gueltig_bis):
                bis_str = ak.gueltig_bis.isoformat() if ak.gueltig_bis else "unbegrenzt"
                warnings.append(
                    f'Zeitliche Überschneidung mit aktivem Schlüssel „{ak.name}" '
                    f"({ak.gueltig_von.isoformat()} – {bis_str})."
                )

        key = AllocationKey(
            org_id=org_id, name=name.strip(), basis=basis, gueltig_von=von, gueltig_bis=bis
        )
        self.db.add(key)
        self.db.flush()
        for p in positions:
            self.db.add(
                AllocationKeyPosition(
                    org_id=org_id,
                    allocation_key_id=key.id,
                    cost_center_id=p["cost_center_id"],
                    prozent=Decimal(str(p["prozent"])),
                )
            )
        self.db.commit()
        self.db.refresh(key)
        return {
            "data": _key_scalars(key),
            "message": f'Verteilungsschlüssel „{key.name}" wurde erfolgreich angelegt.',
            "warnings": warnings,
        }

    # ── neue version ──────────────────────────────────────────────────────────
    def neue_version(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        existing = self.db.execute(
            select(AllocationKey)
            .where(AllocationKey.id == id_, AllocationKey.org_id == org_id)
            .options(selectinload(AllocationKey.positions))
        ).scalar_one_or_none()
        if existing is None:
            raise APIError(404, "NOT_FOUND", "Verteilungsschlüssel nicht gefunden.")

        gv = body.get("gueltig_von")
        if not isinstance(gv, str) or not gv:
            raise APIError(422, "VALIDATION_GUELTIG_VON", "Gültig-von-Datum ist erforderlich.")
        neue_von = _parse_date(gv)
        if neue_von is None:
            raise APIError(422, "VALIDATION_GUELTIG_VON", "Ungültiges Gültig-von-Datum.")
        if neue_von <= existing.gueltig_von:
            raise APIError(
                422,
                "VALIDATION_DATE_ORDER",
                f"Das neue Gültig-von-Datum muss nach dem aktuellen Startdatum "
                f"({existing.gueltig_von.isoformat()}) liegen.",
            )

        positions = self._validate_positions(org_id, body.get("positions"))
        alte_bis = neue_von - timedelta(days=1)

        existing.gueltig_bis = alte_bis
        existing.ist_aktiv = False
        family_root = existing.parent_key_id or existing.id
        new_key = AllocationKey(
            org_id=org_id,
            name=existing.name,
            basis=existing.basis,
            gueltig_von=neue_von,
            gueltig_bis=None,
            ist_aktiv=True,
            parent_key_id=family_root,
        )
        self.db.add(new_key)
        self.db.flush()
        for p in positions:
            self.db.add(
                AllocationKeyPosition(
                    org_id=org_id,
                    allocation_key_id=new_key.id,
                    cost_center_id=p["cost_center_id"],
                    prozent=Decimal(str(p["prozent"])),
                )
            )
        self.db.commit()
        self.db.refresh(new_key)
        return {
            "data": _key_scalars(new_key),
            "message": f'Neue Version von „{new_key.name}" wurde angelegt. Der vorherige '
            "Schlüssel ist jetzt deaktiviert.",
        }

    # ── patch ─────────────────────────────────────────────────────────────────
    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        key = self._get(org_id, id_)
        if key is None:
            raise APIError(404, "NOT_FOUND", "Verteilungsschlüssel nicht gefunden.")
        changed = False
        if "name" in body:
            name = body["name"]
            if not isinstance(name, str) or not (2 <= len(name.strip()) <= 100):
                raise APIError(
                    422, "VALIDATION_NAME", "Name muss zwischen 2 und 100 Zeichen lang sein."
                )
            key.name = name.strip()
            changed = True
        if "gueltig_bis" in body:
            gb = body["gueltig_bis"]
            if gb in (None, ""):
                key.gueltig_bis = None
            else:
                if not isinstance(gb, str):
                    raise APIError(422, "VALIDATION_GUELTIG_BIS", "Ungültiges Gültig-bis-Datum.")
                bis = _parse_date(gb)
                if bis is None:
                    raise APIError(422, "VALIDATION_GUELTIG_BIS", "Ungültiges Gültig-bis-Datum.")
                if bis <= key.gueltig_von:
                    raise APIError(
                        422, "VALIDATION_DATE_ORDER", "Gültig-bis muss nach Gültig-von liegen."
                    )
                key.gueltig_bis = bis
            changed = True
        if not changed:
            raise APIError(422, "NO_CHANGES", "Keine zu aktualisierenden Felder angegeben.")
        self.db.commit()
        self.db.refresh(key)
        return {
            "data": _key_scalars(key),
            "message": "Verteilungsschlüssel wurde aktualisiert.",
        }

    # ── delete (soft) ─────────────────────────────────────────────────────────
    def deactivate(self, org_id: str, id_: str) -> dict[str, Any]:
        key = self._get(org_id, id_)
        if key is None:
            raise APIError(404, "NOT_FOUND", "Verteilungsschlüssel nicht gefunden.")
        if not key.ist_aktiv:
            raise APIError(
                409, "ALREADY_INACTIVE", "Verteilungsschlüssel ist bereits deaktiviert."
            )
        key.ist_aktiv = False
        self.db.commit()
        self.db.refresh(key)
        return {
            "data": _key_scalars(key),
            "message": f'Verteilungsschlüssel „{key.name}" wurde deaktiviert.',
        }
