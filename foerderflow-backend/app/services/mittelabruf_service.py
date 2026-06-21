"""Mittelabrufe — port of app/api/protected/mittelabrufe/*.

list/get/create/update/frist + kalender. POST enforces measure AKTIV + not ABRUF-
Verfahren, fiscal year OPEN, derives verwendungsfrist_tage (body → FundingRule →
42 default), runs the Fehlbedarf compliance limit check, computes frist_bis, and
fires cross-finanzierung recompute (audit). Money → string, dates → YYYY-MM-DD.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.funding import FundingMeasure, FundingRule
from app.models.master import FiscalYear
from app.models.mittelabruf import Mittelabruf
from app.services.audit_service import log_audit
from app.services.fehlbedarf_compliance import (
    check_mittelabruf_allowed,
    recompute_cross_finanzierung_alerts,
)
from app.services.fristen_service import get_frist_status, get_tage_verbleibend
from app.utils.serialization import decimal_str as _dec

VALID_STATUS = ("ABGERUFEN", "VERWENDET", "ABGELAUFEN", "ZURUECKGEZAHLT")


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _d(v) -> str | None:
    return v.isoformat() if v else None


def _abruf(m: Mittelabruf, *, with_measure: bool = True) -> dict[str, Any]:
    row = {
        "id": m.id,
        "org_id": m.org_id,
        "funding_measure_id": m.funding_measure_id,
        "fiscal_year_id": m.fiscal_year_id,
        "abruf_datum": _d(m.abruf_datum),
        "betrag": _dec(m.betrag),
        "verwendungsfrist_tage": m.verwendungsfrist_tage,
        "frist_bis": _d(m.frist_bis),
        "status": _ev(m.status),
        "betrag_verwendet": _dec(m.betrag_verwendet),
        "betrag_zurueck": _dec(m.betrag_zurueck),
        "notiz": m.notiz,
        "created_at": _d(m.created_at),
        "updated_at": _d(m.updated_at),
    }
    if with_measure and m.funding_measure is not None:
        row["funding_measure"] = {
            "name": m.funding_measure.name,
            "funder": {"name": m.funding_measure.funder.name} if m.funding_measure.funder else None,
        }
    return row


class MittelabrufService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, org_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        conds = [Mittelabruf.org_id == org_id]
        if params.get("funding_measure_id"):
            conds.append(Mittelabruf.funding_measure_id == params["funding_measure_id"])
        if params.get("fiscal_year_id"):
            conds.append(Mittelabruf.fiscal_year_id == params["fiscal_year_id"])
        if params.get("status"):
            conds.append(Mittelabruf.status == params["status"])
        rows = (
            self.db.execute(
                select(Mittelabruf)
                .where(*conds)
                .order_by(Mittelabruf.frist_bis.asc())
                .options(
                    selectinload(Mittelabruf.funding_measure).selectinload(FundingMeasure.funder)
                )
            )
            .scalars()
            .all()
        )
        return [_abruf(m) for m in rows]

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        m = self.db.execute(
            select(Mittelabruf)
            .where(Mittelabruf.id == id_, Mittelabruf.org_id == org_id)
            .options(
                selectinload(Mittelabruf.funding_measure).selectinload(FundingMeasure.funder),
                selectinload(Mittelabruf.fiscal_year),
            )
        ).scalar_one_or_none()
        if m is None:
            raise APIError(404, "NOT_FOUND", "Mittelabruf nicht gefunden.")
        row = _abruf(m)
        row["fiscal_year"] = {"jahr": m.fiscal_year.jahr} if m.fiscal_year else None
        row["tage_verbleibend"] = get_tage_verbleibend(m.frist_bis)
        row["frist_status"] = get_frist_status(m.frist_bis, _ev(m.status))
        row["betrag_offen"] = float(m.betrag) - float(m.betrag_verwendet)
        return row

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        fmid = body.get("funding_measure_id")
        if not isinstance(fmid, str) or not fmid:
            raise APIError(422, "VALIDATION_MEASURE", "funding_measure_id fehlt.")
        fyid = body.get("fiscal_year_id")
        if not isinstance(fyid, str) or not fyid:
            raise APIError(422, "VALIDATION_FISCAL_YEAR", "fiscal_year_id fehlt.")
        abruf_datum = body.get("abruf_datum")
        if (
            not isinstance(abruf_datum, str)
            or not re.match(r"^\d{4}-\d{2}-\d{2}$", abruf_datum)
        ):
            raise APIError(
                422, "VALIDATION_DATUM", "abruf_datum muss ein gültiges Datum (YYYY-MM-DD) sein."
            )
        try:
            abruf_date = date.fromisoformat(abruf_datum)
        except ValueError:
            raise APIError(  # noqa: B904
                422, "VALIDATION_DATUM", "abruf_datum muss ein gültiges Datum (YYYY-MM-DD) sein."
            )
        betrag = body.get("betrag")
        if not isinstance(betrag, (int, float)) or isinstance(betrag, bool) or betrag <= 0:
            raise APIError(422, "VALIDATION_BETRAG", "betrag muss eine positive Zahl sein.")

        measure = self.db.execute(
            select(FundingMeasure).where(FundingMeasure.id == fmid, FundingMeasure.org_id == org_id)
        ).scalar_one_or_none()
        if measure is None:
            raise APIError(404, "MEASURE_NOT_FOUND", "Fördermassnahme nicht gefunden.")
        if _ev(measure.status) != "AKTIV":
            raise APIError(400, "MEASURE_NOT_AKTIV", "Fördermassnahme ist nicht aktiv.")
        if _ev(measure.mittelabruf_verfahren) == "ABRUF":
            raise APIError(
                400,
                "ABRUF_VERFAHREN_NOT_SUPPORTED",
                "Diese Fördermassnahme verwendet das ABRUF-Verfahren (tagesgenaue "
                "Auszahlung). Ein separates Anforderungs-Tracking ist dafür nicht "
                "vorgesehen.",
            )

        fy = self.db.execute(
            select(FiscalYear).where(FiscalYear.id == fyid, FiscalYear.org_id == org_id)
        ).scalar_one_or_none()
        if fy is None:
            raise APIError(404, "FISCAL_YEAR_NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        if _ev(fy.status) != "OFFEN":
            raise APIError(400, "FISCAL_YEAR_GESCHLOSSEN", "Haushaltsjahr ist nicht offen.")

        verwendungsfrist_tage = 42
        raw = body.get("verwendungsfrist_tage")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
            verwendungsfrist_tage = round(raw)
        else:
            rule = self.db.execute(
                select(FundingRule).where(
                    FundingRule.funding_measure_id == fmid,
                    FundingRule.typ == "VERWENDUNGSFRIST_TAGE",
                )
            ).scalar_one_or_none()
            if rule and rule.wert:
                try:
                    parsed = int(rule.wert)
                    if parsed > 0:
                        verwendungsfrist_tage = parsed
                except ValueError:
                    pass

        compliance = check_mittelabruf_allowed(self.db, fmid, org_id, float(betrag))
        if not compliance.allowed:
            log_audit(
                self.db,
                org_id=org_id,
                aktion="COMPLIANCE_ALERT_BLOCKED_ABRUF",
                entitaet="FundingMeasure",
                entitaet_id=fmid,
                nachher={
                    "abrufBetrag": betrag,
                    "verbleibend": compliance.verbleibend,
                    "reason": compliance.reason,
                },
            )
            raise APIError(
                422,
                "MITTELABRUF_LIMIT_UEBERSCHRITTEN",
                f"Abruf nicht möglich: beantragter Betrag {betrag:.2f} € überschreitet "
                f"den verbleibend abrufbaren Betrag von {compliance.verbleibend:.2f} € "
                f"(ANBest-P §2.2)."
                + (f" Aufschlüsselung: {compliance.reason}." if compliance.reason else ""),
                extra={
                    "details": {
                        "beantragt": betrag,
                        "verbleibend": compliance.verbleibend,
                        "reason": compliance.reason,
                    }
                },
            )

        frist_bis = abruf_date + timedelta(days=verwendungsfrist_tage)
        m = Mittelabruf(
            org_id=org_id,
            funding_measure_id=fmid,
            fiscal_year_id=fyid,
            abruf_datum=abruf_date,
            betrag=betrag,
            verwendungsfrist_tage=verwendungsfrist_tage,
            frist_bis=frist_bis,
            notiz=body.get("notiz") if isinstance(body.get("notiz"), str) else None,
        )
        self.db.add(m)
        self.db.commit()

        # cross-finanzierung recompute (fire-and-forget; audit per affected measure)
        try:
            affected = recompute_cross_finanzierung_alerts(self.db, fmid, org_id)
            for aid in affected:
                log_audit(
                    self.db,
                    org_id=org_id,
                    aktion="COMPLIANCE_CROSS_RECOMPUTE",
                    entitaet="FundingMeasure",
                    entitaet_id=aid,
                    nachher={
                        "triggered_by_mittelabruf_id": m.id,
                        "triggered_by_funding_measure_id": fmid,
                    },
                )
        except Exception:  # noqa: BLE001
            self.db.rollback()

        m = self.db.execute(
            select(Mittelabruf)
            .where(Mittelabruf.id == m.id)
            .options(
                selectinload(Mittelabruf.funding_measure).selectinload(FundingMeasure.funder)
            )
        ).scalar_one()
        return _abruf(m)

    def update(self, org_id: str, user_id: str | None, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        m = self.db.execute(
            select(Mittelabruf).where(Mittelabruf.id == id_, Mittelabruf.org_id == org_id)
        ).scalar_one_or_none()
        if m is None:
            raise APIError(404, "NOT_FOUND", "Mittelabruf nicht gefunden.")

        status = body.get("status")
        betrag_verwendet = body.get("betrag_verwendet")
        betrag_zurueck = body.get("betrag_zurueck")
        notiz = body.get("notiz")

        if status is not None:
            if status not in VALID_STATUS:
                raise APIError(422, "VALIDATION_STATUS", "Ungültiger Status.")
            if status == "VERWENDET":
                verwendet = (
                    betrag_verwendet
                    if isinstance(betrag_verwendet, (int, float)) and not isinstance(betrag_verwendet, bool)
                    else float(m.betrag_verwendet)
                )
                if verwendet < float(m.betrag):
                    raise APIError(
                        422,
                        "VALIDATION_VERWENDET",
                        "betrag_verwendet muss mindestens dem abgerufenen Betrag entsprechen, "
                        "um als verwendet zu markieren.",
                    )
            if status == "ZURUECKGEZAHLT":
                if not isinstance(betrag_zurueck, (int, float)) or isinstance(betrag_zurueck, bool) or betrag_zurueck <= 0:
                    raise APIError(
                        422, "VALIDATION_ZURUECK", "betrag_zurueck ist Pflicht bei Rückzahlung."
                    )

        vorher = {
            "status": _ev(m.status),
            "betrag_verwendet": _dec(m.betrag_verwendet),
            "betrag_zurueck": _dec(m.betrag_zurueck),
        }
        if status is not None:
            m.status = status
        if isinstance(betrag_verwendet, (int, float)) and not isinstance(betrag_verwendet, bool):
            m.betrag_verwendet = betrag_verwendet
        if isinstance(betrag_zurueck, (int, float)) and not isinstance(betrag_zurueck, bool):
            m.betrag_zurueck = betrag_zurueck
        if isinstance(notiz, str):
            m.notiz = notiz
        self.db.commit()
        self.db.refresh(m)
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="MITTELABRUF_UPDATE",
            entitaet="Mittelabruf",
            entitaet_id=id_,
            vorher=vorher,
            nachher={
                "status": _ev(m.status),
                "betrag_verwendet": _dec(m.betrag_verwendet),
                "betrag_zurueck": _dec(m.betrag_zurueck),
            },
        )
        return _abruf(m, with_measure=False)

    def update_frist(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        m = self.db.execute(
            select(Mittelabruf).where(Mittelabruf.id == id_, Mittelabruf.org_id == org_id)
        ).scalar_one_or_none()
        if m is None:
            raise APIError(404, "NOT_FOUND", "Mittelabruf nicht gefunden.")
        if _ev(m.status) != "ABGERUFEN":
            raise APIError(
                400,
                "STATUS_NOT_ABGERUFEN",
                "Die Frist kann nur bei Abrufen mit Status ABGERUFEN geändert werden.",
            )
        vt = body.get("verwendungsfrist_tage")
        if not isinstance(vt, int) or isinstance(vt, bool) or vt < 1 or vt > 180:
            raise APIError(
                422,
                "VALIDATION_FRIST",
                "verwendungsfrist_tage muss eine ganze Zahl zwischen 1 und 180 sein.",
            )
        m.verwendungsfrist_tage = vt
        m.frist_bis = m.abruf_datum + timedelta(days=vt)
        self.db.commit()
        self.db.refresh(m)
        return _abruf(m, with_measure=False)

    # ── kalender (Python aggregation; cross-dialect) ──────────────────────────
    def kalender(self, org_id: str, haushaltsjahr_id: str | None, periode: str) -> dict[str, Any]:
        if not haushaltsjahr_id:
            raise APIError(400, "MISSING_PARAMS", "haushaltsjahr_id ist erforderlich.")
        hj = self.db.execute(
            select(FiscalYear).where(FiscalYear.id == haushaltsjahr_id, FiscalYear.org_id == org_id)
        ).scalar_one_or_none()
        if hj is None:
            raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        is_quarter = periode == "QUARTAL"

        rows = (
            self.db.execute(
                select(Mittelabruf)
                .where(
                    Mittelabruf.org_id == org_id,
                    Mittelabruf.fiscal_year_id == haushaltsjahr_id,
                )
                .options(
                    selectinload(Mittelabruf.funding_measure).selectinload(FundingMeasure.funder)
                )
            )
            .scalars()
            .all()
        )

        periods: dict[str, dict[str, Any]] = {}
        for m in rows:
            fb = m.frist_bis
            if is_quarter:
                start_month = (fb.month - 1) // 3 * 3 + 1
                p_start = date(fb.year, start_month, 1)
                q = (start_month - 1) // 3 + 1
                label = f"Q{q} {fb.year}"
                end_month = start_month + 2
                p_end = _end_of_month(fb.year, end_month)
            else:
                p_start = date(fb.year, fb.month, 1)
                label = _german_month(fb.month) + f" {fb.year}"
                p_end = _end_of_month(fb.year, fb.month)
            key = p_start.isoformat()
            funder = m.funding_measure.funder if m.funding_measure else None
            funder_id = funder.id if funder else "—"
            funder_name = funder.name if funder else "—"

            entry = periods.setdefault(
                key,
                {
                    "label": label,
                    "start": p_start.isoformat(),
                    "ende": p_end.isoformat(),
                    "_funder": {},
                    "gesamt_abgerufen": 0.0,
                    "gesamt_verwendet": 0.0,
                },
            )
            f = entry["_funder"].setdefault(
                funder_id,
                {
                    "funder_id": funder_id,
                    "funder_name": funder_name,
                    "_abgerufen": 0.0,
                    "_verwendet": 0.0,
                    "anzahl": 0,
                },
            )
            f["_abgerufen"] += float(m.betrag)
            f["_verwendet"] += float(m.betrag_verwendet)
            f["anzahl"] += 1
            entry["gesamt_abgerufen"] += float(m.betrag)
            entry["gesamt_verwendet"] += float(m.betrag_verwendet)

        perioden = []
        for key in sorted(periods.keys()):
            e = periods[key]
            funders = sorted(e["_funder"].values(), key=lambda x: x["funder_name"])
            perioden.append(
                {
                    "label": e["label"],
                    "start": e["start"],
                    "ende": e["ende"],
                    "funder": [
                        {
                            "funder_id": f["funder_id"],
                            "funder_name": f["funder_name"],
                            "betrag_abgerufen": f"{f['_abgerufen']:.2f}",
                            "betrag_verwendet": f"{f['_verwendet']:.2f}",
                            "betrag_offen": f"{f['_abgerufen'] - f['_verwendet']:.2f}",
                            "anzahl": f["anzahl"],
                        }
                        for f in funders
                    ],
                    "gesamt_abgerufen": f"{e['gesamt_abgerufen']:.2f}",
                    "gesamt_verwendet": f"{e['gesamt_verwendet']:.2f}",
                }
            )
        return {"perioden": perioden, "haushaltsjahr": {"id": hj.id, "jahr": hj.jahr}}


def _end_of_month(year: int, month: int) -> date:
    if month >= 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


_GERMAN_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _german_month(month: int) -> str:
    return _GERMAN_MONTHS[month - 1]
