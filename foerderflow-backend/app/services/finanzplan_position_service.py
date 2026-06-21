"""Finanzplan-Positionen — port of app/api/protected/finanzplan-positionen/*.

Money fields serialize as NUMBERS here (the monolith uses Number()), unlike the
funding-measure endpoints (strings). Handles Verwaltungspauschale (FIXER_BETRAG /
PROZENT_GESAMT / PROZENT_PERSONAL / UMLAGE_KOSTENSTELLEN) validation incl. the
recursion guard and Umlage FK consistency, kostenbereich resolution/replacement,
and the Doppelförderung soft-check.
"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.allocation import AllocationKey, AllocationKeyPosition, UmlageSourceScope
from app.models.enums import PauschaleTyp
from app.models.finanzplan import FinanzplanPosition, FinanzplanPositionKostenbereich
from app.models.funding import FundingMeasure
from app.models.master import CostCenter
from app.services.finanzplan_kostenbereich import resolve_kostenbereiche
from app.services.pauschale_doppelfoerderung import (
    check_pauschale_doppelfoerderung,
    format_doppelfoerderung_warnings,
)

VALID_PAUSCHALE_TYPEN = (
    "FIXER_BETRAG",
    "PROZENT_GESAMT",
    "PROZENT_PERSONAL",
    "UMLAGE_KOSTENSTELLEN",
)


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _kb_link(link: FinanzplanPositionKostenbereich, brief: bool) -> dict[str, Any]:
    kb = link.kostenbereich
    if brief:
        kb_ser: dict[str, Any] = {"code": kb.code, "bezeichnung": kb.bezeichnung}
    else:
        kb_ser = {
            "id": kb.id,
            "code": kb.code,
            "bezeichnung": kb.bezeichnung,
            "beschreibung": kb.beschreibung,
            "parent_id": kb.parent_id,
            "org_id": kb.org_id,
            "ist_aktiv": kb.ist_aktiv,
            "skr42_konto_von": kb.skr42_konto_von,
            "skr42_konto_bis": kb.skr42_konto_bis,
            "ist_personal": kb.ist_personal,
            "ist_gemeinkosten": kb.ist_gemeinkosten,
            "belegpflicht_default": kb.belegpflicht_default,
            "foerderfahig_default": kb.foerderfahig_default,
            "sort_order": kb.sort_order,
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        }
    return {
        "id": link.id,
        "org_id": link.org_id,
        "finanzplan_position_id": link.finanzplan_position_id,
        "kostenbereich_id": link.kostenbereich_id,
        "foerderfahig_anteil": float(link.foerderfahig_anteil),
        "cap_betrag": float(link.cap_betrag) if link.cap_betrag is not None else None,
        "hinweis": link.hinweis,
        "kostenbereich": kb_ser,
    }


def _position_scalars(p: FinanzplanPosition) -> dict[str, Any]:
    return {
        "id": p.id,
        "org_id": p.org_id,
        "funding_measure_id": p.funding_measure_id,
        "positionscode": p.positionscode,
        "bezeichnung": p.bezeichnung,
        "betrag_bewilligt": float(p.betrag_bewilligt),
        "deckungsfaehigkeit_pool": p.deckungsfaehigkeit_pool,
        "ueberziehung_limit_pct": float(p.ueberziehung_limit_pct),
        "ueberziehung_genehmigungspflichtig": p.ueberziehung_genehmigungspflichtig,
        "foerderfahigkeit_hinweis": p.foerderfahigkeit_hinweis,
        "eigenanteil_typ": _ev(p.eigenanteil_typ) if p.eigenanteil_typ else None,
        "ist_pauschale": p.ist_pauschale,
        "pauschale_typ": _ev(p.pauschale_typ) if p.pauschale_typ else None,
        "pauschale_prozent": float(p.pauschale_prozent) if p.pauschale_prozent is not None else None,
        "umlage_allocation_key_id": p.umlage_allocation_key_id,
        "umlage_ziel_cost_center_id": p.umlage_ziel_cost_center_id,
        "umlage_source_scope_id": p.umlage_source_scope_id,
        "sort_order": p.sort_order,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


class FinanzplanPositionService:
    def __init__(self, db: Session):
        self.db = db

    def _measure(self, org_id: str, measure_id: str) -> FundingMeasure | None:
        return self.db.execute(
            select(FundingMeasure).where(
                FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none()

    # ── list ──────────────────────────────────────────────────────────────────
    def list(self, org_id: str, funding_measure_id: str | None) -> list[dict[str, Any]]:
        if not funding_measure_id:
            raise APIError(400, "MISSING_PARAM", "funding_measure_id ist erforderlich.")
        if self._measure(org_id, funding_measure_id) is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
        positions = (
            self.db.execute(
                select(FinanzplanPosition)
                .where(
                    FinanzplanPosition.funding_measure_id == funding_measure_id,
                    FinanzplanPosition.org_id == org_id,
                )
                .options(
                    selectinload(FinanzplanPosition.kostenbereiche).selectinload(
                        FinanzplanPositionKostenbereich.kostenbereich
                    ),
                    selectinload(FinanzplanPosition.fund_allocations),
                )
                .order_by(FinanzplanPosition.sort_order.asc())
            )
            .scalars()
            .all()
        )
        rows = []
        for p in positions:
            row = _position_scalars(p)
            row["kostenbereiche"] = [_kb_link(k, brief=True) for k in p.kostenbereiche]
            row["_count"] = {"fund_allocations": len(p.fund_allocations)}
            rows.append(row)
        return rows

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        p = self.db.execute(
            select(FinanzplanPosition)
            .where(FinanzplanPosition.id == id_, FinanzplanPosition.org_id == org_id)
            .options(
                selectinload(FinanzplanPosition.kostenbereiche).selectinload(
                    FinanzplanPositionKostenbereich.kostenbereich
                ),
                selectinload(FinanzplanPosition.funding_measure),
                selectinload(FinanzplanPosition.fund_allocations),
                selectinload(FinanzplanPosition.haushaltsplan_posten),
            )
        ).scalar_one_or_none()
        if p is None:
            raise APIError(404, "NOT_FOUND", "Finanzplanposition nicht gefunden.")
        row = _position_scalars(p)
        row["kostenbereiche"] = [_kb_link(k, brief=False) for k in p.kostenbereiche]
        row["funding_measure"] = {
            "name": p.funding_measure.name,
            "funder_id": p.funding_measure.funder_id,
        }
        row["_count"] = {
            "fund_allocations": len(p.fund_allocations),
            "haushaltsplan_posten": len(p.haushaltsplan_posten),
        }
        return row

    # ── pauschale validation (shared by create) ───────────────────────────────
    def _validate_umlage(
        self, org_id: str, alloc_key: str | None, ziel_kst: str | None, scope: str | None
    ) -> None:
        if not alloc_key or not ziel_kst or not scope:
            raise APIError(
                422,
                "VALIDATION_UMLAGE_FKS",
                "UMLAGE_KOSTENSTELLEN benötigt alle 3 Felder: umlage_allocation_key_id, "
                "umlage_ziel_cost_center_id, umlage_source_scope_id.",
            )
        if self.db.execute(
            select(AllocationKey.id).where(AllocationKey.id == alloc_key, AllocationKey.org_id == org_id)
        ).scalar_one_or_none() is None:
            raise APIError(422, "VALIDATION_UMLAGE_KEY", "Verteilungsschlüssel nicht gefunden.")
        if self.db.execute(
            select(CostCenter.id).where(CostCenter.id == ziel_kst, CostCenter.org_id == org_id)
        ).scalar_one_or_none() is None:
            raise APIError(422, "VALIDATION_UMLAGE_ZIEL", "Ziel-Kostenstelle nicht gefunden.")
        if self.db.execute(
            select(UmlageSourceScope.id).where(
                UmlageSourceScope.id == scope, UmlageSourceScope.org_id == org_id
            )
        ).scalar_one_or_none() is None:
            raise APIError(422, "VALIDATION_UMLAGE_SCOPE", "Quell-KST-Pool nicht gefunden.")
        ziel_in_key = self.db.execute(
            select(AllocationKeyPosition.id).where(
                AllocationKeyPosition.allocation_key_id == alloc_key,
                AllocationKeyPosition.cost_center_id == ziel_kst,
            )
        ).scalar_one_or_none()
        if ziel_in_key is None:
            raise APIError(
                422,
                "VALIDATION_UMLAGE_ZIEL_NOT_IN_KEY",
                "Ziel-Kostenstelle ist nicht Teil des gewählten Verteilungsschlüssels "
                "— kein Anteil ableitbar.",
            )

    # ── create ────────────────────────────────────────────────────────────────
    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        fmid = body.get("funding_measure_id")
        if not isinstance(fmid, str) or not fmid:
            raise APIError(422, "VALIDATION_MEASURE", "funding_measure_id ist erforderlich.")
        measure = self._measure(org_id, fmid)
        if measure is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")

        positionscode = body.get("positionscode")
        if not isinstance(positionscode, str) or not positionscode.strip():
            raise APIError(422, "VALIDATION_CODE", "Positionscode ist erforderlich.")
        bezeichnung = body.get("bezeichnung")
        if not isinstance(bezeichnung, str) or not bezeichnung.strip():
            raise APIError(422, "VALIDATION_BEZEICHNUNG", "Bezeichnung ist erforderlich.")

        betrag = _num(body.get("betrag_bewilligt"))
        if math.isnan(betrag) or betrag < 0:
            raise APIError(
                422, "VALIDATION_BETRAG", "Betrag bewilligt muss eine nicht-negative Zahl sein."
            )

        kb_entries = resolve_kostenbereiche(self.db, body.get("kostenbereiche"))

        ist_pauschale = body.get("ist_pauschale") is True
        pauschale_typ_norm = (
            body["pauschale_typ"].upper()
            if isinstance(body.get("pauschale_typ"), str)
            else None
        )
        pauschale_prozent = (
            body["pauschale_prozent"]
            if _is_num(body.get("pauschale_prozent")) and math.isfinite(body["pauschale_prozent"])
            else None
        )
        umlage_key = body["umlage_allocation_key_id"].strip() if isinstance(body.get("umlage_allocation_key_id"), str) and body["umlage_allocation_key_id"].strip() else None
        umlage_ziel = body["umlage_ziel_cost_center_id"].strip() if isinstance(body.get("umlage_ziel_cost_center_id"), str) and body["umlage_ziel_cost_center_id"].strip() else None
        umlage_scope = body["umlage_source_scope_id"].strip() if isinstance(body.get("umlage_source_scope_id"), str) and body["umlage_source_scope_id"].strip() else None

        if ist_pauschale:
            if not pauschale_typ_norm or pauschale_typ_norm not in VALID_PAUSCHALE_TYPEN:
                raise APIError(
                    422,
                    "VALIDATION_PAUSCHALE_TYP",
                    "Pauschale-Typ erforderlich: FIXER_BETRAG, PROZENT_GESAMT, "
                    "PROZENT_PERSONAL oder UMLAGE_KOSTENSTELLEN.",
                )
            if (
                pauschale_typ_norm in ("PROZENT_GESAMT", "PROZENT_PERSONAL")
                and pauschale_prozent is None
            ):
                if measure.verwaltungspauschale_prozent is None:
                    raise APIError(
                        422,
                        "VALIDATION_PAUSCHALE_PROZENT",
                        f"Prozent-Wert erforderlich für {pauschale_typ_norm}. Entweder pro "
                        "Position oder als Maßnahmen-Default (verwaltungspauschale_prozent) setzen.",
                    )
            if pauschale_typ_norm == "PROZENT_GESAMT":
                existing = self.db.execute(
                    select(FinanzplanPosition).where(
                        FinanzplanPosition.funding_measure_id == fmid,
                        FinanzplanPosition.org_id == org_id,
                        FinanzplanPosition.ist_pauschale.is_(True),
                        FinanzplanPosition.pauschale_typ == PauschaleTyp.PROZENT_GESAMT,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    raise APIError(
                        422,
                        "VALIDATION_PAUSCHALE_REKURSION",
                        "Pro Maßnahme nur eine Position mit pauschale_typ=PROZENT_GESAMT "
                        f'erlaubt (Rekursionsschutz). Position „{existing.bezeichnung}" '
                        "existiert bereits.",
                    )
            if pauschale_typ_norm == "UMLAGE_KOSTENSTELLEN":
                self._validate_umlage(org_id, umlage_key, umlage_ziel, umlage_scope)

        is_umlage = ist_pauschale and pauschale_typ_norm == "UMLAGE_KOSTENSTELLEN"
        pos = FinanzplanPosition(
            org_id=org_id,
            funding_measure_id=fmid,
            positionscode=positionscode.strip(),
            bezeichnung=bezeichnung.strip(),
            betrag_bewilligt=betrag,
            deckungsfaehigkeit_pool=(
                body["deckungsfaehigkeit_pool"].strip()
                if isinstance(body.get("deckungsfaehigkeit_pool"), str)
                and body["deckungsfaehigkeit_pool"].strip()
                else None
            ),
            ueberziehung_limit_pct=(
                body["ueberziehung_limit_pct"] if _is_num(body.get("ueberziehung_limit_pct")) else 20
            ),
            ueberziehung_genehmigungspflichtig=(
                body["ueberziehung_genehmigungspflichtig"]
                if isinstance(body.get("ueberziehung_genehmigungspflichtig"), bool)
                else False
            ),
            foerderfahigkeit_hinweis=(
                body["foerderfahigkeit_hinweis"].strip()
                if isinstance(body.get("foerderfahigkeit_hinweis"), str)
                and body["foerderfahigkeit_hinweis"].strip()
                else None
            ),
            sort_order=body["sort_order"] if _is_num(body.get("sort_order")) else 0,
            ist_pauschale=ist_pauschale,
            pauschale_typ=pauschale_typ_norm if ist_pauschale else None,
            pauschale_prozent=pauschale_prozent if ist_pauschale else None,
            umlage_allocation_key_id=umlage_key if is_umlage else None,
            umlage_ziel_cost_center_id=umlage_ziel if is_umlage else None,
            umlage_source_scope_id=umlage_scope if is_umlage else None,
        )
        self.db.add(pos)
        self.db.flush()
        for e in kb_entries:
            self.db.add(
                FinanzplanPositionKostenbereich(
                    org_id=org_id,
                    finanzplan_position_id=pos.id,
                    kostenbereich_id=e.kostenbereich_id,
                    foerderfahig_anteil=e.foerderfahig_anteil,
                    cap_betrag=e.cap_betrag,
                    hinweis=e.hinweis,
                )
            )
        self.db.commit()
        self.db.refresh(pos)

        result: dict[str, Any] = {
            "data": _position_scalars(pos),
            "message": f'Position „{pos.bezeichnung}" wurde erfolgreich angelegt.',
        }
        if is_umlage and umlage_key and umlage_ziel and umlage_scope:
            warnings = format_doppelfoerderung_warnings(
                check_pauschale_doppelfoerderung(
                    self.db, org_id, None, umlage_key, umlage_ziel, umlage_scope
                )
            )
            if warnings:
                result["warnings"] = warnings
        return result

    # ── update ────────────────────────────────────────────────────────────────
    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        pos = self.db.execute(
            select(FinanzplanPosition).where(
                FinanzplanPosition.id == id_, FinanzplanPosition.org_id == org_id
            )
        ).scalar_one_or_none()
        if pos is None:
            raise APIError(404, "NOT_FOUND", "Finanzplanposition nicht gefunden.")

        has = lambda k: k in body  # noqa: E731
        new_pauschale_typ = (
            body["pauschale_typ"].upper()
            if has("pauschale_typ") and isinstance(body.get("pauschale_typ"), str)
            else (None if has("pauschale_typ") else "__keep__")
        )
        new_ist_pauschale = (
            (body["ist_pauschale"] is True) if has("ist_pauschale") else None
        )

        def _norm_umlage(key: str):
            if not has(key):
                return "__keep__"
            v = body[key]
            return v.strip() if isinstance(v, str) and v.strip() else None

        umlage_key = _norm_umlage("umlage_allocation_key_id")
        umlage_ziel = _norm_umlage("umlage_ziel_cost_center_id")
        umlage_scope = _norm_umlage("umlage_source_scope_id")

        eff_ist_pauschale = new_ist_pauschale if new_ist_pauschale is not None else pos.ist_pauschale
        eff_typ = (
            new_pauschale_typ
            if new_pauschale_typ != "__keep__"
            else (_ev(pos.pauschale_typ) if pos.pauschale_typ else None)
        )

        if eff_ist_pauschale and eff_typ == "UMLAGE_KOSTENSTELLEN":
            eff_key = umlage_key if umlage_key != "__keep__" else pos.umlage_allocation_key_id
            eff_ziel = umlage_ziel if umlage_ziel != "__keep__" else pos.umlage_ziel_cost_center_id
            eff_scope = umlage_scope if umlage_scope != "__keep__" else pos.umlage_source_scope_id
            if not eff_key or not eff_ziel or not eff_scope:
                raise APIError(
                    422,
                    "VALIDATION_UMLAGE_FKS",
                    "UMLAGE_KOSTENSTELLEN benötigt alle 3 Felder: umlage_allocation_key_id, "
                    "umlage_ziel_cost_center_id, umlage_source_scope_id.",
                )
            # org-scope checks only for newly provided FKs
            for key_id, model, col in (
                (umlage_key, AllocationKey, "alloc"),
                (umlage_ziel, CostCenter, "cc"),
                (umlage_scope, UmlageSourceScope, "scope"),
            ):
                if key_id not in ("__keep__", None):
                    ok = self.db.execute(
                        select(model.id).where(model.id == key_id, model.org_id == org_id)
                    ).scalar_one_or_none()
                    if ok is None:
                        raise APIError(
                            422,
                            "VALIDATION_UMLAGE_ORG",
                            "Mindestens eine UMLAGE-Referenz gehört nicht zur Org oder "
                            "existiert nicht.",
                        )
            ziel_in_key = self.db.execute(
                select(AllocationKeyPosition.id).where(
                    AllocationKeyPosition.allocation_key_id == eff_key,
                    AllocationKeyPosition.cost_center_id == eff_ziel,
                )
            ).scalar_one_or_none()
            if ziel_in_key is None:
                raise APIError(
                    422,
                    "VALIDATION_UMLAGE_ZIEL_NOT_IN_KEY",
                    "Ziel-Kostenstelle ist nicht Teil des gewählten Verteilungsschlüssels "
                    "— kein Anteil ableitbar.",
                )

        kb_entries = (
            resolve_kostenbereiche(self.db, body["kostenbereiche"])
            if has("kostenbereiche")
            else None
        )

        if has("positionscode") and isinstance(body["positionscode"], str):
            pos.positionscode = body["positionscode"].strip()
        if has("bezeichnung") and isinstance(body["bezeichnung"], str):
            pos.bezeichnung = body["bezeichnung"].strip()
        if has("betrag_bewilligt"):
            pos.betrag_bewilligt = _num(body["betrag_bewilligt"])
        if has("deckungsfaehigkeit_pool"):
            v = body["deckungsfaehigkeit_pool"]
            pos.deckungsfaehigkeit_pool = v.strip() if isinstance(v, str) and v.strip() else None
        if _is_num(body.get("ueberziehung_limit_pct")):
            pos.ueberziehung_limit_pct = body["ueberziehung_limit_pct"]
        if isinstance(body.get("ueberziehung_genehmigungspflichtig"), bool):
            pos.ueberziehung_genehmigungspflichtig = body["ueberziehung_genehmigungspflichtig"]
        if has("foerderfahigkeit_hinweis"):
            v = body["foerderfahigkeit_hinweis"]
            pos.foerderfahigkeit_hinweis = v.strip() if isinstance(v, str) and v.strip() else None
        if _is_num(body.get("sort_order")):
            pos.sort_order = body["sort_order"]
        if has("ist_pauschale"):
            pos.ist_pauschale = body["ist_pauschale"] is True
        if has("pauschale_typ"):
            pos.pauschale_typ = (
                new_pauschale_typ
                if new_pauschale_typ in VALID_PAUSCHALE_TYPEN
                else None
            )
        if has("pauschale_prozent"):
            v = body["pauschale_prozent"]
            pos.pauschale_prozent = v if _is_num(v) and math.isfinite(v) else None

        # Umlage FK persistence (auto-reset when effective type != UMLAGE)
        if eff_typ == "UMLAGE_KOSTENSTELLEN":
            if umlage_key != "__keep__":
                pos.umlage_allocation_key_id = umlage_key
            if umlage_ziel != "__keep__":
                pos.umlage_ziel_cost_center_id = umlage_ziel
            if umlage_scope != "__keep__":
                pos.umlage_source_scope_id = umlage_scope
        else:
            pos.umlage_allocation_key_id = None
            pos.umlage_ziel_cost_center_id = None
            pos.umlage_source_scope_id = None

        if kb_entries is not None:
            self.db.query(FinanzplanPositionKostenbereich).filter(
                FinanzplanPositionKostenbereich.finanzplan_position_id == id_
            ).delete(synchronize_session=False)
            for e in kb_entries:
                self.db.add(
                    FinanzplanPositionKostenbereich(
                        org_id=org_id,
                        finanzplan_position_id=id_,
                        kostenbereich_id=e.kostenbereich_id,
                        foerderfahig_anteil=e.foerderfahig_anteil,
                        cap_betrag=e.cap_betrag,
                        hinweis=e.hinweis,
                    )
                )
        self.db.commit()
        self.db.refresh(pos)

        result: dict[str, Any] = {"data": _position_scalars(pos)}
        if (
            pos.ist_pauschale
            and _ev(pos.pauschale_typ) == "UMLAGE_KOSTENSTELLEN"
            and pos.umlage_allocation_key_id
            and pos.umlage_ziel_cost_center_id
            and pos.umlage_source_scope_id
        ):
            warnings = format_doppelfoerderung_warnings(
                check_pauschale_doppelfoerderung(
                    self.db,
                    org_id,
                    id_,
                    pos.umlage_allocation_key_id,
                    pos.umlage_ziel_cost_center_id,
                    pos.umlage_source_scope_id,
                )
            )
            if warnings:
                result["warnings"] = warnings
        return result

    # ── deckungsfähigkeit ──────────────────────────────────────────────────────
    def _pool_ist(self, org_id: str, funding_measure_id: str, position_ids: list[str]) -> float:
        """Σ weighted fund-allocation actuals for pool positions via the canonical
        allocation→position resolver (Override ∪ Bridge path), matching
        lib/foerderfahigkeit.berechneDeckunsfaehigkeit."""
        from sqlalchemy import func

        from app.services.allocation_position_resolver import (
            allocation_to_position_subquery,
        )

        if not position_ids:
            return 0.0
        resolved = allocation_to_position_subquery(funding_measure_id, org_id)
        total = self.db.execute(
            select(func.coalesce(func.sum(resolved.c.gewichteter_betrag), 0))
            .select_from(resolved)
            .join(
                FinanzplanPosition,
                FinanzplanPosition.id == resolved.c.effective_finanzplan_position_id,
            )
            .where(
                resolved.c.effective_finanzplan_position_id.in_(position_ids),
                FinanzplanPosition.ist_pauschale.is_(False),
            )
        ).scalar_one()
        return float(total or 0)

    def deckungsfaehigkeit(self, org_id: str, id_: str) -> dict[str, Any]:
        p = self.db.execute(
            select(FinanzplanPosition).where(
                FinanzplanPosition.id == id_, FinanzplanPosition.org_id == org_id
            )
        ).scalar_one_or_none()
        if p is None:
            raise APIError(404, "NOT_FOUND", "Finanzplanposition nicht gefunden.")
        if not p.deckungsfaehigkeit_pool:
            return {
                "data": {
                    "pool": None,
                    "pool_gesamt_bewilligt": float(p.betrag_bewilligt),
                    "pool_gesamt_ist": None,
                    "deckungsfaehig": None,
                    "hinweis": "Diese Position ist nicht deckungsfähig mit anderen Positionen.",
                }
            }
        pool_positions = (
            self.db.execute(
                select(FinanzplanPosition)
                .where(
                    FinanzplanPosition.funding_measure_id == p.funding_measure_id,
                    FinanzplanPosition.deckungsfaehigkeit_pool == p.deckungsfaehigkeit_pool,
                    FinanzplanPosition.org_id == org_id,
                )
                .order_by(FinanzplanPosition.sort_order.asc())
            )
            .scalars()
            .all()
        )
        pool_bewilligt = sum(
            float(pp.betrag_bewilligt) * (1 + float(pp.ueberziehung_limit_pct) / 100)
            for pp in pool_positions
        )
        pool_ist = self._pool_ist(
            org_id, p.funding_measure_id, [pp.id for pp in pool_positions]
        )
        return {
            "data": {
                "pool": p.deckungsfaehigkeit_pool,
                "pool_positionen": [
                    {
                        "id": pp.id,
                        "positionscode": pp.positionscode,
                        "bezeichnung": pp.bezeichnung,
                        "betrag_bewilligt": float(pp.betrag_bewilligt),
                        "ueberziehung_limit_pct": float(pp.ueberziehung_limit_pct),
                    }
                    for pp in pool_positions
                ],
                "pool_gesamt_bewilligt": pool_bewilligt,
                "pool_gesamt_ist": pool_ist,
                "deckungsfaehig": pool_ist <= pool_bewilligt,
            }
        }

    # ── delete ────────────────────────────────────────────────────────────────
    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        pos = self.db.execute(
            select(FinanzplanPosition)
            .where(FinanzplanPosition.id == id_, FinanzplanPosition.org_id == org_id)
            .options(selectinload(FinanzplanPosition.fund_allocations))
        ).scalar_one_or_none()
        if pos is None:
            raise APIError(404, "NOT_FOUND", "Finanzplanposition nicht gefunden.")
        n = len(pos.fund_allocations)
        if n > 0:
            raise APIError(
                409,
                "HAS_ALLOCATIONS",
                f"Position kann nicht gelöscht werden — {n} Zuordnung(en) vorhanden.",
            )
        self.db.delete(pos)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Position wurde gelöscht."}
