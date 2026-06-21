"""Fördermassnahmen (FundingMeasure) — port of app/api/protected/foerdermassnahmen/*.

The domain core: create/list/get/update/delete with the monolith's exact validation
codes, Decimal→string serialization, expiry computation, rule + cost-center
replacement, status locking (ABGESCHLOSSEN → only WIDERRUFEN), and soft/hard delete.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.funding import FundingMeasure
from app.repositories.funding_measure_repository import FundingMeasureRepository
from app.services.foerdermassnahme_zeitraum import validate_durchfuehrungszeitraum

VALID_STATUS = ("AKTIV", "ABGESCHLOSSEN", "WIDERRUFEN")
VALID_VERFAHREN = ("ANFORDERUNG", "ABRUF", "ABSCHLAG")
VALID_RULE_TYPEN = (
    "KOSTENKATEGORIE_ERLAUBT",
    "KOSTENKATEGORIE_VERBOTEN",
    "BELEGPFLICHT_SPEZIAL",
    "EIGENANTEIL_MIN",
    "VERWENDUNGSFRIST_TAGE",
    "ZWISCHENNACHWEIS_PFLICHT",
    "PERSONALKOSTEN_HOECHSTSATZ",
)
VALID_FINANZIERUNGSART = ("ANTEIL", "FEHLBEDARF", "FESTBETRAG")
VALID_EIGENANTEIL_TYP = ("KOFINANZIERUNG", "NICHT_FOERDERFAHIGER_OVERHEAD")

_MISSING = object()


def js_number(v: Any) -> float:
    """Mimic JS Number() coercion enough for the monolith's numeric validation."""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


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


from app.utils.serialization import decimal_str as _dec  # noqa: E402


def _ev(v: Any) -> Any:
    """Enum value, tolerant of plain strings (identity-map may hold the raw str
    assigned before a DB round-trip)."""
    return v.value if hasattr(v, "value") else v


def _compute_expiry(laufzeit_bis: date) -> dict[str, Any]:
    diff = (laufzeit_bis - date.today()).days
    return {
        "is_expired": diff < 0,
        "days_until_expiry": diff if diff >= 0 else None,
    }


def _scalars(m: FundingMeasure) -> dict[str, Any]:
    return {
        "id": m.id,
        "org_id": m.org_id,
        "funder_id": m.funder_id,
        "name": m.name,
        "budget_gesamt": _dec(m.budget_gesamt),
        "foerderquote": _dec(m.foerderquote),
        "laufzeit_von": m.laufzeit_von.isoformat(),
        "laufzeit_bis": m.laufzeit_bis.isoformat(),
        "durchfuehrungs_von": m.durchfuehrungs_von.isoformat() if m.durchfuehrungs_von else None,
        "durchfuehrungs_bis": m.durchfuehrungs_bis.isoformat() if m.durchfuehrungs_bis else None,
        "antragsnummer": m.antragsnummer,
        "verwaltungspauschale_erlaubt": m.verwaltungspauschale_erlaubt,
        "verwaltungspauschale_prozent": _dec(m.verwaltungspauschale_prozent),
        "budget_flexibilitaet_prozent": _dec(m.budget_flexibilitaet_prozent),
        "overhead_limit_prozent": _dec(m.overhead_limit_prozent),
        "mwst_foerderfahig": m.mwst_foerderfahig,
        "mwst_satz_prozent": _dec(m.mwst_satz_prozent),
        "mittelabruf_verfahren": _ev(m.mittelabruf_verfahren),
        "status": _ev(m.status),
        "foerderkennzeichen": m.foerderkennzeichen,
        "finanzierungsart": _ev(m.finanzierungsart) if m.finanzierungsart else None,
        "eigenanteil_typ": _ev(m.eigenanteil_typ) if m.eigenanteil_typ else None,
        "eigenmittel_betrag": _dec(m.eigenmittel_betrag),
        "drittmittel_betrag": _dec(m.drittmittel_betrag),
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        **_compute_expiry(m.laufzeit_bis),
    }


def _funder_brief(m: FundingMeasure) -> dict[str, Any]:
    return {"id": m.funder.id, "name": m.funder.name, "typ": _ev(m.funder.typ)}


def _funder_full(m: FundingMeasure) -> dict[str, Any]:
    f = m.funder
    return {
        "id": f.id,
        "org_id": f.org_id,
        "name": f.name,
        "typ": _ev(f.typ),
        "notizen": f.notizen,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


def _rule(r) -> dict[str, Any]:
    return {
        "id": r.id,
        "org_id": r.org_id,
        "funding_measure_id": r.funding_measure_id,
        "typ": _ev(r.typ),
        "schluessel": r.schluessel,
        "wert": r.wert,
        "beschreibung": r.beschreibung,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _cc_link_full(link) -> dict[str, Any]:
    cc = link.cost_center
    return {
        "id": link.id,
        "org_id": link.org_id,
        "funding_measure_id": link.funding_measure_id,
        "cost_center_id": link.cost_center_id,
        "created_at": link.created_at.isoformat() if link.created_at else None,
        "cost_center": {
            "id": cc.id,
            "name": cc.name,
            "code": cc.code,
            "typ": _ev(cc.typ),
            "ist_aktiv": cc.ist_aktiv,
        },
    }


class FoerdermassnahmeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FundingMeasureRepository(db)

    # ── list ──────────────────────────────────────────────────────────────────
    def list(
        self, org_id: str, status_filter: str | None, funder_id: str | None
    ) -> list[dict[str, Any]]:
        eff_status = status_filter if status_filter in VALID_STATUS else None
        measures = self.repo.list_filtered(org_id, eff_status, funder_id)
        spend = self._spend_by_measure(org_id, [m.id for m in measures])
        rows = []
        for m in measures:
            row = _scalars(m)
            row["funder"] = _funder_brief(m)
            row["cost_centers"] = [
                {"cost_center_id": link.cost_center_id} for link in m.cost_centers
            ]
            row["_count"] = {"rules": len(m.rules), "cost_centers": len(m.cost_centers)}
            row["cost_center_ids"] = [link.cost_center_id for link in m.cost_centers]
            # betrag_ist = Σ fund_allocations.betrag_foerderung (batch, matches monolith list)
            row["betrag_ist"] = float(spend.get(m.id, Decimal(0)))
            rows.append(row)
        return rows

    def _spend_by_measure(self, org_id: str, measure_ids: list[str]) -> dict[str, Decimal]:
        if not measure_ids:
            return {}
        from sqlalchemy import func, select

        from app.models.transaction import FundAllocation

        rows = self.db.execute(
            select(
                FundAllocation.funding_measure_id,
                func.coalesce(func.sum(FundAllocation.betrag_foerderung), 0),
            )
            .where(
                FundAllocation.org_id == org_id,
                FundAllocation.funding_measure_id.in_(measure_ids),
            )
            .group_by(FundAllocation.funding_measure_id)
        ).all()
        return {mid: Decimal(str(total)) for mid, total in rows}

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        m = self.repo.get_full(org_id, id_)
        if m is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Fördermassnahme nicht gefunden."
            )
        return self._serialize_full(m, funder_full=True)

    def _serialize_full(self, m: FundingMeasure, funder_full: bool) -> dict[str, Any]:
        row = _scalars(m)
        row["funder"] = _funder_full(m) if funder_full else _funder_brief(m)
        rules = sorted(m.rules, key=lambda r: _ev(r.typ))
        row["rules"] = [_rule(r) for r in rules]
        row["cost_centers"] = [_cc_link_full(link) for link in m.cost_centers]
        row["_count"] = {"rules": len(m.rules), "cost_centers": len(m.cost_centers)}
        return row

    # ── create ─────────────────────────────────────────────────────────────────
    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        funder_id = body.get("funder_id")
        if not isinstance(funder_id, str) or not funder_id.strip():
            raise APIError(422, "VALIDATION_FUNDER", "Fördergeber ist erforderlich.")

        name = body.get("name")
        if not isinstance(name, str) or not (2 <= len(name.strip()) <= 300):
            raise APIError(
                422, "VALIDATION_NAME", "Name muss zwischen 2 und 300 Zeichen lang sein."
            )

        budget = js_number(body.get("budget_gesamt"))
        if not math.isfinite(budget) or budget <= 0:
            raise APIError(
                422, "VALIDATION_BUDGET", "Budget gesamt muss eine positive Zahl sein."
            )

        fq = js_number(body.get("foerderquote"))
        if not math.isfinite(fq) or fq < 0 or fq > 100:
            raise APIError(
                422, "VALIDATION_FOERDERQUOTE", "Förderquote muss zwischen 0 und 100 liegen."
            )

        lv_raw, lb_raw = body.get("laufzeit_von"), body.get("laufzeit_bis")
        laufzeit_von = _parse_date(lv_raw)
        if laufzeit_von is None:
            raise APIError(
                422, "VALIDATION_LAUFZEIT_VON", "Laufzeit von ist kein gültiges Datum."
            )
        laufzeit_bis = _parse_date(lb_raw)
        if laufzeit_bis is None:
            raise APIError(
                422, "VALIDATION_LAUFZEIT_BIS", "Laufzeit bis ist kein gültiges Datum."
            )
        if laufzeit_von >= laufzeit_bis:
            raise APIError(
                422,
                "VALIDATION_LAUFZEIT_RANGE",
                "Bewilligungszeitraum: Beginn muss vor Ende liegen.",
            )

        zr = validate_durchfuehrungszeitraum(
            laufzeit_von, laufzeit_bis, body.get("durchfuehrungs_von"), body.get("durchfuehrungs_bis")
        )
        if not zr.ok:
            raise APIError(422, zr.code, zr.message)

        antragsnummer = body.get("antragsnummer")
        antragsnummer_value: str | None = None
        if antragsnummer not in (None, ""):
            if not isinstance(antragsnummer, str) or len(antragsnummer.strip()) > 100:
                raise APIError(
                    422,
                    "VALIDATION_ANTRAGSNUMMER",
                    "Antragsnummer darf maximal 100 Zeichen lang sein.",
                )
            antragsnummer_value = antragsnummer.strip()

        status_val = body.get("status", "AKTIV")
        if status_val not in VALID_STATUS:
            raise APIError(
                422, "VALIDATION_STATUS", f"Ungültiger Status. Erlaubt: {', '.join(VALID_STATUS)}."
            )

        verfahren = body.get("mittelabruf_verfahren")
        if verfahren not in VALID_VERFAHREN:
            raise APIError(
                422,
                "VALIDATION_VERFAHREN",
                f"Ungültiges Mittelabruf-Verfahren. Erlaubt: {', '.join(VALID_VERFAHREN)}.",
            )

        vp_erlaubt = body.get("verwaltungspauschale_erlaubt", False) is True
        pauschale_proz: float | None = None
        if vp_erlaubt:
            vpp = body.get("verwaltungspauschale_prozent")
            if vpp is not None:
                n = js_number(vpp)
                if not math.isfinite(n) or n < 0 or n > 100:
                    raise APIError(
                        422,
                        "VALIDATION_PAUSCHALE",
                        "Verwaltungspauschale muss zwischen 0 und 100 Prozent liegen.",
                    )
                pauschale_proz = n

        flex = js_number(body.get("budget_flexibilitaet_prozent", 20))
        if not math.isfinite(flex) or flex < 0 or flex > 100:
            raise APIError(
                422,
                "VALIDATION_FLEXIBILITAET",
                "Budget-Flexibilität muss zwischen 0 und 100 Prozent liegen.",
            )

        overhead = body.get("overhead_limit_prozent")
        overhead_val: float | None = None
        if overhead is not None:
            overhead_val = js_number(overhead)
            if not math.isfinite(overhead_val) or overhead_val < 0 or overhead_val > 100:
                raise APIError(
                    422,
                    "VALIDATION_OVERHEAD_LIMIT",
                    "Gemeinkostendeckel muss zwischen 0 und 100 Prozent liegen.",
                )

        funder = self._funder_exists(org_id, funder_id)
        if funder is None:
            raise APIError(
                422,
                "FUNDER_NOT_FOUND",
                "Fördergeber nicht gefunden oder gehört nicht zu dieser Organisation.",
            )

        rules = body.get("rules", [])
        if not isinstance(rules, list):
            raise APIError(422, "VALIDATION_RULES", "Regeln müssen ein Array sein.")
        for rule in rules:
            if rule.get("typ") not in VALID_RULE_TYPEN:
                raise APIError(
                    422, "VALIDATION_RULE_TYP", f"Ungültiger Regeltyp: {rule.get('typ')}"
                )
            if not isinstance(rule.get("schluessel"), str) or not rule["schluessel"].strip():
                raise APIError(
                    422,
                    "VALIDATION_RULE_SCHLUESSEL",
                    "Jede Regel benötigt einen Schlüssel.",
                )

        cost_center_ids = body.get("cost_center_ids", [])
        if not isinstance(cost_center_ids, list):
            raise APIError(
                422,
                "VALIDATION_COST_CENTERS",
                "Kostenstellen müssen ein Array von IDs sein.",
            )
        if cost_center_ids:
            existing = self.repo.cost_center_ids_existing(org_id, cost_center_ids)
            if len(existing) != len(set(cost_center_ids)):
                raise APIError(
                    422,
                    "COST_CENTER_NOT_FOUND",
                    "Eine oder mehrere Kostenstellen wurden nicht gefunden oder gehören "
                    "nicht zu dieser Organisation.",
                )

        finanzierungsart = body.get("finanzierungsart")
        eigenmittel = None
        drittmittel = None
        if finanzierungsart == "FEHLBEDARF":
            em = body.get("eigenmittel_betrag")
            if em is not None:
                n = js_number(em)
                eigenmittel = n if math.isfinite(n) and n >= 0 else None
            dm = body.get("drittmittel_betrag")
            if dm is not None:
                n = js_number(dm)
                drittmittel = n if math.isfinite(n) and n >= 0 else None

        mwst_satz = js_number(body.get("mwst_satz_prozent", 19)) or 19

        m = FundingMeasure(
            org_id=org_id,
            funder_id=funder_id,
            name=name.strip(),
            budget_gesamt=Decimal(str(budget)),
            foerderquote=Decimal(str(fq)),
            laufzeit_von=laufzeit_von,
            laufzeit_bis=laufzeit_bis,
            durchfuehrungs_von=zr.durchfuehrungs_von,
            durchfuehrungs_bis=zr.durchfuehrungs_bis,
            antragsnummer=antragsnummer_value,
            status=status_val,
            verwaltungspauschale_erlaubt=vp_erlaubt,
            verwaltungspauschale_prozent=(
                Decimal(str(pauschale_proz)) if pauschale_proz is not None else None
            ),
            budget_flexibilitaet_prozent=Decimal(str(flex)),
            overhead_limit_prozent=(
                Decimal(str(overhead_val)) if overhead_val is not None else None
            ),
            mwst_foerderfahig=body.get("mwst_foerderfahig", True) is not False,
            mwst_satz_prozent=Decimal(str(mwst_satz)),
            mittelabruf_verfahren=verfahren,
            finanzierungsart=finanzierungsart or None,
            eigenmittel_betrag=Decimal(str(eigenmittel)) if eigenmittel is not None else None,
            drittmittel_betrag=Decimal(str(drittmittel)) if drittmittel is not None else None,
        )
        self.db.add(m)
        self.db.flush()
        if rules:
            self.repo.replace_rules(
                org_id, m.id, [
                    {
                        "typ": r["typ"],
                        "schluessel": r["schluessel"].strip(),
                        "wert": str(r["wert"]) if r.get("wert") is not None else None,
                        "beschreibung": str(r["beschreibung"]) if r.get("beschreibung") is not None else None,
                    }
                    for r in rules
                ],
            )
        if cost_center_ids:
            self.repo.replace_cost_centers(org_id, m.id, cost_center_ids)
        self.db.commit()
        m = self.repo.get_full(org_id, m.id)
        return self._serialize_full(m, funder_full=False)

    def _funder_exists(self, org_id: str, funder_id: str):
        from app.models.master import Funder
        from sqlalchemy import select

        return self.db.execute(
            select(Funder).where(Funder.id == funder_id, Funder.org_id == org_id)
        ).scalar_one_or_none()

    # ── update ──────────────────────────────────────────────────────────────────
    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        existing = self.repo.get_plain(org_id, id_)
        if existing is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Fördermassnahme nicht gefunden."
            )

        # ABGESCHLOSSEN: only WIDERRUFEN allowed
        if _ev(existing.status) == "ABGESCHLOSSEN":
            if body.get("status") != "WIDERRUFEN":
                raise APIError(
                    422,
                    "STATUS_LOCKED",
                    "Eine abgeschlossene Fördermassnahme kann nur noch widerrufen werden. "
                    "Andere Änderungen sind nicht erlaubt.",
                )
            existing.status = "WIDERRUFEN"
            self.db.commit()
            m = self.repo.get_full(org_id, id_)
            return self._serialize_full(m, funder_full=True)

        has = lambda k: k in body  # noqa: E731

        if has("funder_id"):
            fid = body["funder_id"]
            if not isinstance(fid, str) or not fid.strip():
                raise APIError(422, "VALIDATION_FUNDER", "Ungültige Fördergeber-ID.")
            if self._funder_exists(org_id, fid) is None:
                raise APIError(422, "FUNDER_NOT_FOUND", "Fördergeber nicht gefunden.")
            existing.funder_id = fid

        if has("name"):
            name = body["name"]
            if not isinstance(name, str) or not (2 <= len(name.strip()) <= 300):
                raise APIError(
                    422, "VALIDATION_NAME", "Name muss zwischen 2 und 300 Zeichen lang sein."
                )
            existing.name = name.strip()

        if has("budget_gesamt"):
            n = js_number(body["budget_gesamt"])
            if not math.isfinite(n) or n <= 0:
                raise APIError(
                    422, "VALIDATION_BUDGET", "Budget gesamt muss eine positive Zahl sein."
                )
            existing.budget_gesamt = Decimal(str(n))

        if has("foerderquote"):
            n = js_number(body["foerderquote"])
            if not math.isfinite(n) or n < 0 or n > 100:
                raise APIError(
                    422, "VALIDATION_FOERDERQUOTE", "Förderquote muss zwischen 0 und 100 liegen."
                )
            existing.foerderquote = Decimal(str(n))

        von_date = existing.laufzeit_von
        bis_date = existing.laufzeit_bis
        if has("laufzeit_von"):
            d = _parse_date(body["laufzeit_von"])
            if d is None:
                raise APIError(
                    422, "VALIDATION_LAUFZEIT_VON", "Laufzeit von ist kein gültiges Datum."
                )
            von_date = d
        if has("laufzeit_bis"):
            d = _parse_date(body["laufzeit_bis"])
            if d is None:
                raise APIError(
                    422, "VALIDATION_LAUFZEIT_BIS", "Laufzeit bis ist kein gültiges Datum."
                )
            bis_date = d
        if von_date >= bis_date:
            raise APIError(
                422,
                "VALIDATION_LAUFZEIT_RANGE",
                "Bewilligungszeitraum: Beginn muss vor Ende liegen.",
            )
        if has("laufzeit_von"):
            existing.laufzeit_von = von_date
        if has("laufzeit_bis"):
            existing.laufzeit_bis = bis_date

        if has("durchfuehrungs_von") or has("durchfuehrungs_bis"):
            von_input = body["durchfuehrungs_von"] if has("durchfuehrungs_von") else existing.durchfuehrungs_von
            bis_input = body["durchfuehrungs_bis"] if has("durchfuehrungs_bis") else existing.durchfuehrungs_bis
            zr = validate_durchfuehrungszeitraum(von_date, bis_date, von_input, bis_input)
            if not zr.ok:
                raise APIError(422, zr.code, zr.message)
            existing.durchfuehrungs_von = zr.durchfuehrungs_von
            existing.durchfuehrungs_bis = zr.durchfuehrungs_bis

        if has("antragsnummer"):
            a = body["antragsnummer"]
            if a is None or a == "":
                existing.antragsnummer = None
            else:
                if not isinstance(a, str) or len(a.strip()) > 100:
                    raise APIError(
                        422,
                        "VALIDATION_ANTRAGSNUMMER",
                        "Antragsnummer darf maximal 100 Zeichen lang sein.",
                    )
                existing.antragsnummer = a.strip()

        if has("status"):
            if body["status"] not in VALID_STATUS:
                raise APIError(
                    422, "VALIDATION_STATUS", f"Ungültiger Status. Erlaubt: {', '.join(VALID_STATUS)}."
                )
            existing.status = body["status"]

        if has("verwaltungspauschale_erlaubt"):
            existing.verwaltungspauschale_erlaubt = body["verwaltungspauschale_erlaubt"] is True
            if body["verwaltungspauschale_erlaubt"] is not True:
                existing.verwaltungspauschale_prozent = None

        if has("verwaltungspauschale_prozent"):
            vpp = body["verwaltungspauschale_prozent"]
            if vpp is None:
                existing.verwaltungspauschale_prozent = None
            else:
                if not existing.verwaltungspauschale_erlaubt:
                    raise APIError(
                        422,
                        "VALIDATION_PAUSCHALE",
                        "Verwaltungspauschale-Prozent kann nur gesetzt werden wenn "
                        "Verwaltungspauschale erlaubt ist.",
                    )
                n = js_number(vpp)
                if not math.isfinite(n) or n < 0 or n > 100:
                    raise APIError(
                        422,
                        "VALIDATION_PAUSCHALE",
                        "Verwaltungspauschale muss zwischen 0 und 100 Prozent liegen.",
                    )
                existing.verwaltungspauschale_prozent = Decimal(str(n))

        if has("budget_flexibilitaet_prozent"):
            n = js_number(body["budget_flexibilitaet_prozent"])
            if not math.isfinite(n) or n < 0 or n > 100:
                raise APIError(
                    422,
                    "VALIDATION_FLEXIBILITAET",
                    "Budget-Flexibilität muss zwischen 0 und 100 Prozent liegen.",
                )
            existing.budget_flexibilitaet_prozent = Decimal(str(n))

        if has("mittelabruf_verfahren"):
            if body["mittelabruf_verfahren"] not in VALID_VERFAHREN:
                raise APIError(
                    422,
                    "VALIDATION_VERFAHREN",
                    f"Ungültiges Mittelabruf-Verfahren. Erlaubt: {', '.join(VALID_VERFAHREN)}.",
                )
            existing.mittelabruf_verfahren = body["mittelabruf_verfahren"]

        if has("overhead_limit_prozent"):
            o = body["overhead_limit_prozent"]
            if o is None:
                existing.overhead_limit_prozent = None
            else:
                n = js_number(o)
                if not math.isfinite(n) or n < 0 or n > 100:
                    raise APIError(
                        422,
                        "VALIDATION_OVERHEAD_LIMIT",
                        "Gemeinkostendeckel muss zwischen 0 und 100 Prozent liegen.",
                    )
                existing.overhead_limit_prozent = Decimal(str(n))

        if has("mwst_foerderfahig"):
            existing.mwst_foerderfahig = body["mwst_foerderfahig"] is not False
        if has("mwst_satz_prozent"):
            n = js_number(body["mwst_satz_prozent"])
            if not math.isfinite(n) or n < 0 or n > 100:
                raise APIError(
                    422, "VALIDATION_MWST_SATZ", "MwSt-Satz muss zwischen 0 und 100 liegen."
                )
            existing.mwst_satz_prozent = Decimal(str(n))

        if has("foerderkennzeichen"):
            fk = body["foerderkennzeichen"]
            existing.foerderkennzeichen = fk.strip() if isinstance(fk, str) and fk.strip() else None

        if has("finanzierungsart"):
            fa = body["finanzierungsart"]
            if fa is not None and fa not in VALID_FINANZIERUNGSART:
                raise APIError(
                    422,
                    "VALIDATION_FINANZIERUNGSART",
                    f"Ungültige Finanzierungsart. Erlaubt: {', '.join(VALID_FINANZIERUNGSART)}.",
                )
            existing.finanzierungsart = fa or None

        if has("eigenanteil_typ"):
            et = body["eigenanteil_typ"]
            if et is not None and et not in VALID_EIGENANTEIL_TYP:
                raise APIError(
                    422,
                    "VALIDATION_EIGENANTEIL_TYP",
                    f"Ungültiger Eigenanteil-Typ. Erlaubt: {', '.join(VALID_EIGENANTEIL_TYP)}.",
                )
            existing.eigenanteil_typ = et or None

        if has("eigenmittel_betrag"):
            em = body["eigenmittel_betrag"]
            if em is None:
                existing.eigenmittel_betrag = None
            else:
                n = js_number(em)
                if not math.isfinite(n) or n < 0:
                    raise APIError(
                        422,
                        "VALIDATION_EIGENMITTEL_BETRAG",
                        "Eigenmittel-Betrag muss eine positive Zahl sein.",
                    )
                existing.eigenmittel_betrag = Decimal(str(n))

        if has("drittmittel_betrag"):
            dm = body["drittmittel_betrag"]
            if dm is None:
                existing.drittmittel_betrag = None
            else:
                n = js_number(dm)
                if not math.isfinite(n) or n < 0:
                    raise APIError(
                        422,
                        "VALIDATION_DRITTMITTEL_BETRAG",
                        "Drittmittel-Betrag muss eine positive Zahl sein.",
                    )
                existing.drittmittel_betrag = Decimal(str(n))

        if isinstance(body.get("rules"), list):
            self.repo.replace_rules(
                org_id, id_, [
                    {
                        "typ": r["typ"],
                        "schluessel": r["schluessel"],
                        "wert": r.get("wert"),
                        "beschreibung": r.get("beschreibung"),
                    }
                    for r in body["rules"]
                ],
            )
        if isinstance(body.get("cost_center_ids"), list):
            self.repo.replace_cost_centers(org_id, id_, body["cost_center_ids"])

        self.db.commit()
        m = self.repo.get_full(org_id, id_)
        return self._serialize_full(m, funder_full=True)

    # ── delete ──────────────────────────────────────────────────────────────────
    def delete(self, org_id: str, id_: str, hard: bool) -> dict[str, Any]:
        existing = self.repo.get_plain(org_id, id_)
        if existing is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Fördermassnahme nicht gefunden."
            )
        if hard:
            allocations = self.repo.fund_allocation_count(id_)
            mittelabrufe = self.repo.mittelabruf_count(id_)
            blocker = []
            if allocations > 0:
                blocker.append(f"{allocations} Förderzuordnung(en)")
            if mittelabrufe > 0:
                blocker.append(f"{mittelabrufe} Mittelabruf(-e)")
            if blocker:
                raise APIError(
                    409,
                    "HAS_RELATED_DATA",
                    f"Löschen nicht möglich. Es sind noch verknüpft: {', '.join(blocker)}. "
                    "Bitte zuerst entfernen.",
                )
            name = existing.name
            # Core delete so PostgreSQL FK ON DELETE CASCADE handles rules,
            # cost_centers, nachweis_template, bescheid, finanzplan_* (matches the
            # monolith's Prisma cascade). RESTRICT FKs (fund_allocations,
            # mittelabrufe — pre-checked above) would block, as in the monolith.
            from sqlalchemy import delete as _delete

            self.db.execute(_delete(FundingMeasure).where(FundingMeasure.id == id_))
            self.db.commit()
            return {
                "data": {"id": id_},
                "message": f'Fördermassnahme „{name}" wurde vollständig gelöscht.',
            }

        if _ev(existing.status) == "WIDERRUFEN":
            raise APIError(
                409, "ALREADY_REVOKED", "Fördermassnahme ist bereits widerrufen."
            )
        name = existing.name
        existing.status = "WIDERRUFEN"
        self.db.commit()
        return {
            "data": {"id": id_, "status": "WIDERRUFEN"},
            "message": f'Fördermassnahme „{name}" wurde widerrufen.',
        }
