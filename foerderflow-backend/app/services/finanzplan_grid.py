"""Finanzplan grid (Positionen × Kostenbereiche × Monate) — port of
lib/finanzplan-grid.ts + the [id]/finanzplan route (GET/POST batch-upsert/DELETE).

betrag_geplant "0" deletes the posten. Decimals serialize as 2-decimal strings
(monolith uses toFixed(2)).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.finanzplan import (
    FinanzplanPosition,
    FinanzplanPositionKostenbereich,
    HaushaltsPlanPosten,
)
from app.models.funding import FundingMeasure

QUELLE_VALUES = ("MANUELL", "PERSONALMODUL", "IMPORT")


def _ev(v):
    return v.value if hasattr(v, "value") else v


def _months_between(from_: date, to: date) -> list[str]:
    out = []
    y, m = from_.year, from_.month
    while (y, m) <= (to.year, to.month):
        out.append(f"{y:04d}-{m:02d}-01")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _is_month_first(iso: str) -> bool:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", iso):
        return False
    try:
        return date.fromisoformat(iso).day == 1
    except ValueError:
        return False


class FinanzplanGridService:
    def __init__(self, db: Session):
        self.db = db

    def load(self, org_id: str, measure_id: str) -> dict[str, Any] | None:
        measure = self.db.execute(
            select(FundingMeasure).where(
                FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none()
        if measure is None:
            return None
        positionen = (
            self.db.execute(
                select(FinanzplanPosition)
                .where(
                    FinanzplanPosition.funding_measure_id == measure_id,
                    FinanzplanPosition.org_id == org_id,
                )
                .order_by(FinanzplanPosition.sort_order.asc())
                .options(
                    selectinload(FinanzplanPosition.kostenbereiche).selectinload(
                        FinanzplanPositionKostenbereich.kostenbereich
                    ),
                    selectinload(FinanzplanPosition.haushaltsplan_posten),
                )
            )
            .scalars()
            .all()
        )
        laufzeit_monate = _months_between(measure.laufzeit_von, measure.laufzeit_bis)

        posten_map: dict[str, dict[str, Any]] = {}
        for pos in positionen:
            for p in pos.haushaltsplan_posten:
                monat = p.fuer_monat.isoformat()
                key = f"{p.finanzplan_position_id}|{p.kostenbereich_id}|{monat}"
                posten_map[key] = {
                    "betrag": float(p.betrag_geplant),
                    "quelle": _ev(p.quelle) or "MANUELL",
                    "posten_id": p.id,
                }

        gesamt_geplant = 0.0
        gesamt_bewilligt = sum(float(p.betrag_bewilligt) for p in positionen)
        data_positionen = []
        for pos in positionen:
            kbs = []
            for fpkb in pos.kostenbereiche:
                summe = 0.0
                monate = []
                for monat in laufzeit_monate:
                    key = f"{pos.id}|{fpkb.kostenbereich_id}|{monat}"
                    entry = posten_map.get(key)
                    betrag = entry["betrag"] if entry else 0.0
                    summe += betrag
                    monate.append(
                        {
                            "fuer_monat": monat,
                            "betrag_geplant": f"{betrag:.2f}",
                            "quelle": entry["quelle"] if entry else "MANUELL",
                            "posten_id": entry["posten_id"] if entry else None,
                        }
                    )
                gesamt_geplant += summe
                kb = fpkb.kostenbereich
                kbs.append(
                    {
                        "kostenbereich_id": kb.id,
                        "kostenbereich_code": kb.code,
                        "kostenbereich_bezeichnung": kb.bezeichnung,
                        "ist_personal": kb.ist_personal,
                        "monate": monate,
                        "summe_geplant": f"{summe:.2f}",
                    }
                )
            data_positionen.append(
                {
                    "id": pos.id,
                    "positionscode": pos.positionscode,
                    "bezeichnung": pos.bezeichnung,
                    "betrag_bewilligt": f"{float(pos.betrag_bewilligt):.2f}",
                    "eigenanteil_typ": _ev(pos.eigenanteil_typ) if pos.eigenanteil_typ else None,
                    "kostenbereiche": kbs,
                }
            )
        return {
            "positionen": data_positionen,
            "laufzeit_monate": laufzeit_monate,
            "gesamt_geplant": f"{gesamt_geplant:.2f}",
            "gesamt_bewilligt": f"{gesamt_bewilligt:.2f}",
            "diff": f"{gesamt_bewilligt - gesamt_geplant:.2f}",
        }

    def _measure_or_error(self, org_id: str, measure_id: str) -> FundingMeasure:
        m = self.db.execute(
            select(FundingMeasure).where(
                FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none()
        if m is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
        if _ev(m.status) == "WIDERRUFEN":
            raise APIError(422, "MEASURE_REVOKED", "Massnahme ist widerrufen — keine Änderungen möglich.")
        return m

    def batch_upsert(self, org_id: str, measure_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._measure_or_error(org_id, measure_id)
        updates = body.get("updates")
        if not isinstance(updates, list):
            raise APIError(400, "VALIDATION_ERROR", "Feld 'updates' muss ein Array sein.")
        for u in updates:
            if not all(
                isinstance(u.get(k), str)
                for k in ("finanzplan_position_id", "kostenbereich_id", "fuer_monat", "betrag_geplant")
            ):
                raise APIError(400, "VALIDATION_ERROR", "Ungültiges Update-Schema.")
            if not _is_month_first(u["fuer_monat"]):
                raise APIError(
                    400,
                    "VALIDATION_ERROR",
                    f"'fuer_monat' muss erster Tag eines Monats sein (YYYY-MM-01): {u['fuer_monat']}",
                )
            try:
                betrag = float(u["betrag_geplant"])
            except ValueError:
                betrag = float("nan")
            if not (betrag == betrag) or betrag < 0:
                raise APIError(400, "VALIDATION_ERROR", f"'betrag_geplant' muss ≥ 0 sein: {u['betrag_geplant']}")

        position_ids = list({u["finanzplan_position_id"] for u in updates})
        valid_positions = (
            self.db.execute(
                select(FinanzplanPosition)
                .where(
                    FinanzplanPosition.id.in_(position_ids),
                    FinanzplanPosition.funding_measure_id == measure_id,
                    FinanzplanPosition.org_id == org_id,
                )
                .options(selectinload(FinanzplanPosition.kostenbereiche))
            )
            .scalars()
            .all()
        )
        valid_pos_ids = {p.id for p in valid_positions}
        valid_kb_by_pos = {
            p.id: {k.kostenbereich_id for k in p.kostenbereiche} for p in valid_positions
        }
        for u in updates:
            if u["finanzplan_position_id"] not in valid_pos_ids:
                raise APIError(
                    400,
                    "VALIDATION_ERROR",
                    f"FinanzplanPosition {u['finanzplan_position_id']} gehört nicht zu dieser Massnahme.",
                )
            if u["kostenbereich_id"] not in valid_kb_by_pos.get(u["finanzplan_position_id"], set()):
                raise APIError(
                    400,
                    "VALIDATION_ERROR",
                    f"Kostenbereich {u['kostenbereich_id']} ist nicht mit FinanzplanPosition "
                    f"{u['finanzplan_position_id']} verknüpft.",
                )

        updated = 0
        deleted = 0
        for u in updates:
            betrag = float(u["betrag_geplant"])
            fuer_monat = date.fromisoformat(u["fuer_monat"])
            existing = self.db.execute(
                select(HaushaltsPlanPosten).where(
                    HaushaltsPlanPosten.funding_measure_id == measure_id,
                    HaushaltsPlanPosten.finanzplan_position_id == u["finanzplan_position_id"],
                    HaushaltsPlanPosten.kostenbereich_id == u["kostenbereich_id"],
                    HaushaltsPlanPosten.fuer_monat == fuer_monat,
                )
            ).scalar_one_or_none()
            if betrag == 0:
                if existing:
                    self.db.delete(existing)
                    deleted += 1
            else:
                if existing:
                    existing.betrag_geplant = betrag
                    existing.quelle = "MANUELL"
                else:
                    self.db.add(
                        HaushaltsPlanPosten(
                            org_id=org_id,
                            funding_measure_id=measure_id,
                            finanzplan_position_id=u["finanzplan_position_id"],
                            kostenbereich_id=u["kostenbereich_id"],
                            fuer_monat=fuer_monat,
                            betrag_geplant=betrag,
                            quelle="MANUELL",
                        )
                    )
                updated += 1
        self.db.commit()
        return {"data": {"updated": updated, "deleted": deleted}}

    def delete(self, org_id: str, measure_id: str, quelle: str | None) -> dict[str, Any]:
        self._measure_or_error(org_id, measure_id)
        if quelle and quelle not in QUELLE_VALUES:
            raise APIError(
                400, "VALIDATION_ERROR", f"'quelle' muss einer von {', '.join(QUELLE_VALUES)} sein."
            )
        conds = [
            HaushaltsPlanPosten.funding_measure_id == measure_id,
            HaushaltsPlanPosten.org_id == org_id,
        ]
        if quelle:
            conds.append(HaushaltsPlanPosten.quelle == quelle)
        rows = self.db.execute(select(HaushaltsPlanPosten).where(and_(*conds))).scalars().all()
        n = len(rows)
        for r in rows:
            self.db.delete(r)
        self.db.commit()
        return {"data": {"deleted": n}}
