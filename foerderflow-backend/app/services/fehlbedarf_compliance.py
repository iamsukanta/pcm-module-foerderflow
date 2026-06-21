"""Fehlbedarf compliance (ANBest-P §2.2 + Vollfinanzierung) — port of
lib/fehlbedarf-compliance.ts.

Active for finanzierungsart=FEHLBEDARF, or FESTBETRAG with foerderquote=100.
fehlbedarf_zulaessig = min(gesamtausgaben_plan − eigenmittel_ist − drittmittel_ist,
zuwendung_hoechstbetrag). Drittmittel-ist via overlap heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.funding import FundingMeasure, FundingMeasureCostCenter
from app.models.master import Kostenbereich
from app.models.mittelabruf import Mittelabruf
from app.models.transaction import FundAllocation, Transaction, TransactionSplit
from app.services.foerdermassnahme_berechnung import berechne_zuwendung

EIGENMITTEL_KOSTENBEREICH_CODES = [
    "EINNAHMEN_PROJEKT",
    "EINNAHMEN_SPENDEN",
    "EINNAHMEN_SONSTIGE",
    "EINNAHMEN_AAG_ERSTATTUNG",
]
ABGERUFEN_STATI = ["ABGERUFEN", "VERWENDET"]


@dataclass
class CheckMittelabrufResult:
    allowed: bool
    verbleibend: float
    reason: str | None = None


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def ist_compliance_relevant(finanzierungsart: str | None, foerderquote: float) -> bool:
    if finanzierungsart == "FEHLBEDARF":
        return True
    if finanzierungsart == "FESTBETRAG" and foerderquote == 100:
        return True
    return False


def _hoechstbetrag(m: FundingMeasure) -> float:
    fa = _ev(m.finanzierungsart)
    if fa == "FESTBETRAG":
        return float(m.budget_gesamt)
    if fa == "FEHLBEDARF":
        return berechne_zuwendung(
            "FEHLBEDARF",
            gesamtausgaben=float(m.budget_gesamt),
            eigenmittel=float(m.eigenmittel_betrag or 0),
            drittmittel=float(m.drittmittel_betrag or 0),
        ).zuwendung
    return float(m.budget_gesamt) * (float(m.foerderquote) / 100)


def compute_fehlbedarf_status(
    *,
    finanzierungsart: str | None,
    foerderquote: float,
    gesamtausgaben_plan: float,
    eigenmittel_plan: float,
    drittmittel_plan: float,
    zuwendung_hoechstbetrag: float,
    eigenmittel_ist: float,
    drittmittel_ist: float,
    zuwendung_abgerufen: float,
) -> dict[str, Any] | None:
    if not ist_compliance_relevant(finanzierungsart, foerderquote):
        return None

    fehlbedarf_zulaessig = min(
        gesamtausgaben_plan - eigenmittel_ist - drittmittel_ist, zuwendung_hoechstbetrag
    )
    verbleibend = max(0.0, fehlbedarf_zulaessig - zuwendung_abgerufen)
    delta_eigen = eigenmittel_ist - eigenmittel_plan
    delta_dritt = drittmittel_ist - drittmittel_plan

    status = "OK"
    nachricht: str | None = None
    meldepflichtig = False

    if zuwendung_abgerufen > fehlbedarf_zulaessig:
        status = "WARNUNG"
        meldepflichtig = True
        ueberschuss = zuwendung_abgerufen - fehlbedarf_zulaessig
        nachricht = (
            f"Zuwendung um {ueberschuss:.2f} € zu hoch abgerufen. Meldepflicht "
            "gegenüber Fördergeber besteht (ANBest-P §2.2). Rückzahlung oder "
            "Verrechnung mit nächster Rate prüfen."
        )
    elif delta_eigen > 0 or delta_dritt > 0:
        status = "HINWEIS"
        meldepflichtig = True
        parts = []
        if delta_eigen > 0:
            parts.append(f"Eigenmittel +{delta_eigen:.2f} €")
        if delta_dritt > 0:
            parts.append(f"Drittmittel +{delta_dritt:.2f} €")
        nachricht = (
            f"{', '.join(parts)} über Plan. Zulässige Zuwendung sinkt entsprechend. "
            "Meldepflicht gegenüber Fördergeber (ANBest-P §2.2)."
        )

    return {
        "status": status,
        "meldepflichtig": meldepflichtig,
        "fehlbedarf_zulaessig": fehlbedarf_zulaessig,
        "verbleibend_abrufbar": verbleibend,
        "delta_eigenmittel": delta_eigen,
        "delta_drittmittel": delta_dritt,
        "nachricht": nachricht,
    }


def _eigenmittel_ist(db: Session, measure_id: str, org_id: str) -> float:
    total = db.execute(
        select(func.coalesce(func.sum(FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100), 0))
        .select_from(FundAllocation)
        .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
        .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
        .join(Kostenbereich, Kostenbereich.id == Transaction.kostenbereich_id)
        .where(
            FundAllocation.funding_measure_id == measure_id,
            FundAllocation.org_id == org_id,
            Kostenbereich.code.in_(EIGENMITTEL_KOSTENBEREICH_CODES),
        )
    ).scalar_one()
    return float(total or 0)


def _zuwendung_abgerufen(db: Session, measure_id: str, org_id: str) -> float:
    total = db.execute(
        select(func.coalesce(func.sum(Mittelabruf.betrag), 0)).where(
            Mittelabruf.funding_measure_id == measure_id,
            Mittelabruf.org_id == org_id,
            Mittelabruf.status.in_(ABGERUFEN_STATI),
        )
    ).scalar_one()
    return float(total or 0)


def _overlapping_measures(db: Session, measure: FundingMeasure) -> list[dict[str, Any]]:
    own_cc = [cc.cost_center_id for cc in measure.cost_centers]
    if not own_cc:
        return []
    candidates = (
        db.execute(
            select(FundingMeasure)
            .where(
                FundingMeasure.org_id == measure.org_id,
                FundingMeasure.id != measure.id,
                FundingMeasure.laufzeit_von <= measure.laufzeit_bis,
                FundingMeasure.laufzeit_bis >= measure.laufzeit_von,
                FundingMeasure.cost_centers.any(
                    FundingMeasureCostCenter.cost_center_id.in_(own_cc)
                ),
            )
            .options(
                selectinload(FundingMeasure.funder),
                selectinload(FundingMeasure.cost_centers).selectinload(
                    FundingMeasureCostCenter.cost_center
                ),
            )
        )
        .scalars()
        .all()
    )
    result = []
    for c in candidates:
        abgerufen = _zuwendung_abgerufen(db, c.id, c.org_id)
        overlap_start = max(measure.laufzeit_von, c.laufzeit_von)
        overlap_end = min(measure.laufzeit_bis, c.laufzeit_bis)
        overlap_tage = max(0, (overlap_end - overlap_start).days + 1)
        shared = [cc.cost_center.code for cc in c.cost_centers if cc.cost_center_id in own_cc]
        result.append(
            {
                "id": c.id,
                "name": c.name,
                "foerdergeber": c.funder.name if c.funder else "—",
                "finanzierungsart": _ev(c.finanzierungsart) or "—",
                "zuwendung_hoechstbetrag": _hoechstbetrag(c),
                "zuwendung_abgerufen": abgerufen,
                "geteilte_cost_center_codes": shared,
                "bewilligungszeitraum_overlap_tage": overlap_tage,
            }
        )
    return result


def get_fehlbedarf_status(db: Session, measure_id: str, org_id: str) -> dict[str, Any] | None:
    measure = db.execute(
        select(FundingMeasure)
        .where(FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id)
        .options(
            selectinload(FundingMeasure.cost_centers),
            selectinload(FundingMeasure.funder),
        )
    ).scalar_one_or_none()
    if measure is None:
        return None
    if not ist_compliance_relevant(_ev(measure.finanzierungsart), float(measure.foerderquote)):
        return None

    gesamtausgaben_plan = float(measure.budget_gesamt)
    eigenmittel_plan = float(measure.eigenmittel_betrag or 0)
    drittmittel_plan = float(measure.drittmittel_betrag or 0)
    hoechstbetrag = _hoechstbetrag(measure)

    eigenmittel_ist = _eigenmittel_ist(db, measure_id, org_id)
    zuwendung_abgerufen = _zuwendung_abgerufen(db, measure_id, org_id)
    overlaps = _overlapping_measures(db, measure)
    drittmittel_ist = sum(o["zuwendung_abgerufen"] for o in overlaps)

    computed = compute_fehlbedarf_status(
        finanzierungsart=_ev(measure.finanzierungsart),
        foerderquote=float(measure.foerderquote),
        gesamtausgaben_plan=gesamtausgaben_plan,
        eigenmittel_plan=eigenmittel_plan,
        drittmittel_plan=drittmittel_plan,
        zuwendung_hoechstbetrag=hoechstbetrag,
        eigenmittel_ist=eigenmittel_ist,
        drittmittel_ist=drittmittel_ist,
        zuwendung_abgerufen=zuwendung_abgerufen,
    )
    if computed is None:
        return None
    return {
        **computed,
        "gesamtausgaben_plan": gesamtausgaben_plan,
        "eigenmittel_plan": eigenmittel_plan,
        "drittmittel_plan": drittmittel_plan,
        "zuwendung_hoechstbetrag": hoechstbetrag,
        "eigenmittel_ist": eigenmittel_ist,
        "drittmittel_ist": drittmittel_ist,
        "zuwendung_abgerufen": zuwendung_abgerufen,
        "andere_fundingmeasures_ueberlappend": overlaps,
    }


def check_mittelabruf_allowed(
    db: Session, measure_id: str, org_id: str, abruf_betrag: float
) -> CheckMittelabrufResult:
    status = get_fehlbedarf_status(db, measure_id, org_id)
    if status is None:
        return CheckMittelabrufResult(True, float("inf"))
    if abruf_betrag <= status["verbleibend_abrufbar"]:
        return CheckMittelabrufResult(True, status["verbleibend_abrufbar"])
    reason_parts = [
        f"Höchstbetrag laut Bescheid: {status['zuwendung_hoechstbetrag']:.2f} €",
        f"bereits abgerufen: {status['zuwendung_abgerufen']:.2f} €",
    ]
    if status["drittmittel_ist"] > 0:
        reason_parts.append(f"Drittmittel (heuristisch): {status['drittmittel_ist']:.2f} €")
    if status["eigenmittel_ist"] > status["eigenmittel_plan"]:
        reason_parts.append(
            f"Eigenmittel-Mehr-Einnahmen: {status['eigenmittel_ist'] - status['eigenmittel_plan']:.2f} €"
        )
    return CheckMittelabrufResult(False, status["verbleibend_abrufbar"], " / ".join(reason_parts))


def recompute_cross_finanzierung_alerts(
    db: Session, triggering_measure_id: str, org_id: str
) -> list[str]:
    triggering = db.execute(
        select(FundingMeasure)
        .where(FundingMeasure.id == triggering_measure_id, FundingMeasure.org_id == org_id)
        .options(selectinload(FundingMeasure.cost_centers))
    ).scalar_one_or_none()
    if triggering is None or not triggering.cost_centers:
        return []
    own_cc = [cc.cost_center_id for cc in triggering.cost_centers]
    candidates = (
        db.execute(
            select(FundingMeasure.id).where(
                FundingMeasure.org_id == org_id,
                FundingMeasure.id != triggering_measure_id,
                FundingMeasure.laufzeit_von <= triggering.laufzeit_bis,
                FundingMeasure.laufzeit_bis >= triggering.laufzeit_von,
                FundingMeasure.cost_centers.any(
                    FundingMeasureCostCenter.cost_center_id.in_(own_cc)
                ),
                (FundingMeasure.finanzierungsart == "FEHLBEDARF")
                | and_(
                    FundingMeasure.finanzierungsart == "FESTBETRAG",
                    FundingMeasure.foerderquote == 100,
                ),
            )
        )
        .scalars()
        .all()
    )
    affected = []
    for cid in candidates:
        status = get_fehlbedarf_status(db, cid, org_id)
        if status and status["status"] != "OK":
            affected.append(cid)
    return affected
