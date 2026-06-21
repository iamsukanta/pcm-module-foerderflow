"""Fördermassnahme sub-resources: funding rules + cost-center links.

Ports:
  GET/POST  /foerdermassnahmen/[id]/regeln
  DELETE    /foerdermassnahmen/[id]/regeln/[ruleId]
  POST/DELETE /foerdermassnahmen/[id]/kostenstellen
All write ops are blocked on WIDERRUFEN measures (MEASURE_REVOKED).
"""

from __future__ import annotations

from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.funding import FundingMeasure, FundingMeasureCostCenter, FundingRule
from app.models.master import CostCenter
from app.services.audit_service import log_audit
from app.services.foerdermassnahme_service import _cc_link_full, _ev, _rule

VALID_RULE_TYPEN = (
    "KOSTENKATEGORIE_ERLAUBT",
    "KOSTENKATEGORIE_VERBOTEN",
    "BELEGPFLICHT_SPEZIAL",
    "EIGENANTEIL_MIN",
    "VERWENDUNGSFRIST_TAGE",
    "ZWISCHENNACHWEIS_PFLICHT",
    "PERSONALKOSTEN_HOECHSTSATZ",
)


class FoerdermassnahmeSubresourceService:
    def __init__(self, db: Session):
        self.db = db

    def _measure(self, org_id: str, measure_id: str) -> FundingMeasure:
        m = self.db.execute(
            select(FundingMeasure).where(
                FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none()
        if m is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Fördermassnahme nicht gefunden."
            )
        return m

    def _assert_not_revoked(self, m: FundingMeasure) -> None:
        if _ev(m.status) == "WIDERRUFEN":
            raise APIError(
                422,
                "MEASURE_REVOKED",
                "Widerrufene Fördermassnahmen können nicht geändert werden.",
            )

    # ── rules ────────────────────────────────────────────────────────────────
    def list_rules(self, org_id: str, measure_id: str) -> list[dict[str, Any]]:
        self._measure(org_id, measure_id)
        rules = (
            self.db.execute(
                select(FundingRule)
                .where(
                    FundingRule.funding_measure_id == measure_id,
                    FundingRule.org_id == org_id,
                )
                .order_by(FundingRule.typ.asc(), FundingRule.schluessel.asc())
            )
            .scalars()
            .all()
        )
        return [_rule(r) for r in rules]

    def create_rule(
        self, org_id: str, user_id: str | None, measure_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        m = self._measure(org_id, measure_id)
        self._assert_not_revoked(m)

        typ = body.get("typ")
        if typ not in VALID_RULE_TYPEN:
            raise APIError(
                422,
                "VALIDATION_TYP",
                f"Ungültiger Regeltyp. Erlaubt: {', '.join(VALID_RULE_TYPEN)}.",
            )
        schluessel = body.get("schluessel")
        if not isinstance(schluessel, str) or not schluessel.strip():
            raise APIError(422, "VALIDATION_SCHLUESSEL", "Schlüssel ist erforderlich.")

        wert = body.get("wert")
        beschreibung = body.get("beschreibung")
        rule = FundingRule(
            org_id=org_id,
            funding_measure_id=measure_id,
            typ=typ,
            schluessel=schluessel.strip(),
            wert=wert.strip() or None if isinstance(wert, str) else None,
            beschreibung=beschreibung.strip() or None if isinstance(beschreibung, str) else None,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="FOERDERMASSNAHME_REGEL_CREATE",
            entitaet="FundingRule",
            entitaet_id=rule.id,
            nachher={
                "id": rule.id,
                "funding_measure_id": measure_id,
                "typ": _ev(rule.typ),
                "schluessel": rule.schluessel,
                "wert": rule.wert,
            },
        )
        return _rule(rule)

    def delete_rule(
        self, org_id: str, user_id: str | None, measure_id: str, rule_id: str
    ) -> dict[str, Any]:
        m = self._measure(org_id, measure_id)
        self._assert_not_revoked(m)
        rule = self.db.execute(
            select(FundingRule).where(
                FundingRule.id == rule_id,
                FundingRule.funding_measure_id == measure_id,
                FundingRule.org_id == org_id,
            )
        ).scalar_one_or_none()
        if rule is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Förderregel nicht gefunden."
            )
        snapshot = {
            "id": rule_id,
            "funding_measure_id": measure_id,
            "typ": _ev(rule.typ),
            "schluessel": rule.schluessel,
            "wert": rule.wert,
        }
        self.db.delete(rule)
        self.db.commit()
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="FOERDERMASSNAHME_REGEL_DELETE",
            entitaet="FundingRule",
            entitaet_id=rule_id,
            vorher=snapshot,
        )
        return {"data": None, "message": "Förderregel wurde entfernt."}

    # ── cost-center links ─────────────────────────────────────────────────────
    def _get_link(
        self, measure_id: str, cost_center_id: str
    ) -> FundingMeasureCostCenter | None:
        return self.db.execute(
            select(FundingMeasureCostCenter).where(
                FundingMeasureCostCenter.funding_measure_id == measure_id,
                FundingMeasureCostCenter.cost_center_id == cost_center_id,
            )
        ).scalar_one_or_none()

    def add_cost_center(
        self, org_id: str, measure_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        m = self._measure(org_id, measure_id)
        self._assert_not_revoked(m)
        cc_id = body.get("cost_center_id")
        if not isinstance(cc_id, str) or not cc_id.strip():
            raise APIError(
                422, "VALIDATION_COST_CENTER_ID", "Kostenstellen-ID ist erforderlich."
            )
        cc = self.db.execute(
            select(CostCenter).where(
                CostCenter.id == cc_id, CostCenter.org_id == org_id
            )
        ).scalar_one_or_none()
        if cc is None:
            raise APIError(
                422,
                "COST_CENTER_NOT_FOUND",
                "Kostenstelle nicht gefunden oder gehört nicht zu dieser Organisation.",
            )
        if self._get_link(measure_id, cc_id):
            raise APIError(
                status.HTTP_409_CONFLICT,
                "COST_CENTER_DUPLICATE",
                f'Kostenstelle „{cc.code}" ist dieser Fördermassnahme bereits zugeordnet.',
            )
        link = FundingMeasureCostCenter(
            org_id=org_id, funding_measure_id=measure_id, cost_center_id=cc_id
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return {
            "data": _cc_link_full(link),
            "message": f'Kostenstelle „{cc.code} – {cc.name}" wurde der Massnahme zugeordnet.',
        }

    def remove_cost_center(
        self, org_id: str, measure_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        m = self._measure(org_id, measure_id)
        self._assert_not_revoked(m)
        cc_id = body.get("cost_center_id")
        if not isinstance(cc_id, str) or not cc_id.strip():
            raise APIError(
                422, "VALIDATION_COST_CENTER_ID", "Kostenstellen-ID ist erforderlich."
            )
        link = self._get_link(measure_id, cc_id)
        if link is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Kostenstellen-Zuordnung nicht gefunden.",
            )
        cc = link.cost_center
        label = f"{cc.code} – {cc.name}"
        self.db.delete(link)
        self.db.commit()
        return {
            "data": None,
            "message": f'Kostenstelle „{label}" wurde entfernt.',
        }
