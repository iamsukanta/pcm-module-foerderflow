"""Soll-Ist per FinanzplanPosition — port of lib/soll-ist-position.ts."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finanzplan import FinanzplanPosition, HaushaltsPlanPosten
from app.models.funding import FundingMeasure
from app.services.finanzplan_ist import aggregate_ist_by_finanzplan_position
from app.services.vzae import berechne_soll_ist_status


def _ev(v):
    return v.value if hasattr(v, "value") else v


def load_soll_ist_position(db: Session, measure_id: str, org_id: str) -> dict[str, Any]:
    positionen = (
        db.execute(
            select(FinanzplanPosition)
            .where(
                FinanzplanPosition.funding_measure_id == measure_id,
                FinanzplanPosition.org_id == org_id,
            )
            .order_by(FinanzplanPosition.sort_order.asc())
        )
        .scalars()
        .all()
    )
    plan_rows = db.execute(
        select(HaushaltsPlanPosten.finanzplan_position_id, func.sum(HaushaltsPlanPosten.betrag_geplant))
        .where(
            HaushaltsPlanPosten.funding_measure_id == measure_id,
            HaushaltsPlanPosten.org_id == org_id,
        )
        .group_by(HaushaltsPlanPosten.finanzplan_position_id)
    ).all()
    ist_by_position = aggregate_ist_by_finanzplan_position(db, measure_id, org_id)
    measure = db.execute(
        select(FundingMeasure).where(FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id)
    ).scalar_one_or_none()
    default_prozent = (
        float(measure.verwaltungspauschale_prozent)
        if measure and measure.verwaltungspauschale_prozent is not None
        else None
    )

    if not positionen:
        return {
            "data": [],
            "gesamt_beantragt": "0.00",
            "gesamt_bewilligt": "0.00",
            "gesamt_ist": "0.00",
            "gesamt_geplant": "0.00",
        }

    plan_by = {pid: float(s or 0) for pid, s in plan_rows if pid}
    gesamt_bewilligt = 0.0
    gesamt_ist = 0.0
    data = []
    for pos in positionen:
        bewilligt = float(pos.betrag_bewilligt)
        geplant = plan_by.get(pos.id, 0.0)
        ist = ist_by_position.get(pos.id, 0.0)
        differenz = bewilligt - ist
        ausschoepfung = (ist / bewilligt * 100) if bewilligt > 0 else 0.0
        gesamt_bewilligt += bewilligt
        gesamt_ist += ist
        data.append(
            {
                "id": pos.id,
                "kostenart": f"{pos.positionscode}: {pos.bezeichnung}",
                "beschreibung": None,
                "betrag_beantragt": f"{bewilligt:.2f}",
                "betrag_bewilligt": f"{bewilligt:.2f}",
                "betrag_ist": f"{ist:.2f}",
                "betrag_geplant": f"{geplant:.2f}",
                "differenz": f"{differenz:.2f}",
                "ausschoepfung_prozent": round(ausschoepfung * 10) / 10,
                "status": berechne_soll_ist_status(bewilligt, ist),
                "ist_pauschale": pos.ist_pauschale,
                "pauschale_typ": _ev(pos.pauschale_typ) if pos.pauschale_typ else None,
                "pauschale_prozent": float(pos.pauschale_prozent) if pos.pauschale_prozent is not None else None,
                "pauschale_default_prozent": default_prozent,
            }
        )
    gesamt_geplant = sum(plan_by.values())
    return {
        "data": data,
        "gesamt_beantragt": f"{gesamt_bewilligt:.2f}",
        "gesamt_bewilligt": f"{gesamt_bewilligt:.2f}",
        "gesamt_ist": f"{gesamt_ist:.2f}",
        "gesamt_geplant": f"{gesamt_geplant:.2f}",
    }
