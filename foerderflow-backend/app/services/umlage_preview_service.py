"""Umlage drilldown preview — port of
foerdermassnahmen/[id]/finanzplan-positionen/[pos_id]/umlage-preview (Phase K).

Transparent breakdown for UMLAGE_KOSTENSTELLEN pauschale positions: active key
version, Maßnahmen-Anteil, source-KST pool, Σ gross bookings on source KSTs
weighted by the valid key version × Anteil, then förderquote/MwSt → betrag_foerderfahig
capped at betrag_bewilligt, plus Doppelförderung soft-warnings.

All money fields serialize as NUMBERS (monolith uses Number()/parseFloat).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.allocation import (
    AllocationKey,
    AllocationKeyPosition,
    UmlageSourceScope,
    UmlageSourceScopeCostCenter,
)
from app.models.finanzplan import FinanzplanPosition
from app.models.master import CostCenter
from app.models.transaction import Transaction, TransactionSplit
from app.services.allocation_betraege import compute_allocation_betraege
from app.services.pauschale_doppelfoerderung import (
    check_pauschale_doppelfoerderung,
    format_doppelfoerderung_warnings,
)


def _ev(v):
    return v.value if hasattr(v, "value") else v


class UmlagePreviewService:
    def __init__(self, db: Session):
        self.db = db

    def preview(self, org_id: str, measure_id: str, pos_id: str) -> dict[str, Any]:
        position = self.db.execute(
            select(FinanzplanPosition)
            .where(
                FinanzplanPosition.id == pos_id,
                FinanzplanPosition.funding_measure_id == measure_id,
                FinanzplanPosition.org_id == org_id,
            )
            .options(
                selectinload(FinanzplanPosition.umlage_allocation_key)
                .selectinload(AllocationKey.positions)
                .selectinload(AllocationKeyPosition.cost_center),
                selectinload(FinanzplanPosition.umlage_ziel_cost_center),
                selectinload(FinanzplanPosition.umlage_source_scope)
                .selectinload(UmlageSourceScope.cost_centers)
                .selectinload(UmlageSourceScopeCostCenter.cost_center),
                selectinload(FinanzplanPosition.funding_measure),
            )
        ).scalar_one_or_none()

        if position is None:
            raise APIError(404, "NOT_FOUND", "Pauschale-Position nicht gefunden.")

        if _ev(position.pauschale_typ) != "UMLAGE_KOSTENSTELLEN":
            raise APIError(400, "NOT_UMLAGE", "Nur für UMLAGE_KOSTENSTELLEN-Pauschalen verfügbar.")

        ak = position.umlage_allocation_key
        ziel = position.umlage_ziel_cost_center
        scope = position.umlage_source_scope
        if (
            not position.umlage_allocation_key_id
            or not position.umlage_ziel_cost_center_id
            or not position.umlage_source_scope_id
            or ak is None
            or ziel is None
            or scope is None
        ):
            raise APIError(422, "INCOMPLETE_UMLAGE", "UMLAGE-Konfiguration unvollständig.")

        family_root_id = ak.parent_key_id or ak.id

        # Anteil aus Schlüssel für Ziel-KST
        ziel_key_pos = next(
            (p for p in ak.positions if p.cost_center_id == position.umlage_ziel_cost_center_id),
            None,
        )
        anteil_prozent = float(ziel_key_pos.prozent) if ziel_key_pos else 0.0

        # Quell-KSTs (sortiert nach code)
        quell_ccs = sorted(
            (c.cost_center for c in scope.cost_centers), key=lambda cc: cc.code
        )
        quell_ksts = [
            {"id": cc.id, "code": cc.code, "name": cc.name, "typ": _ev(cc.typ)}
            for cc in quell_ccs
        ]
        quell_ids = [k["id"] for k in quell_ksts]

        # Pro Quell-KST: Σ Brutto-Buchungen × Anteil der gültigen Schlüssel-Version
        rows = self.db.execute(
            select(
                TransactionSplit.cost_center_id.label("quell_cc_id"),
                CostCenter.code.label("quell_cc_code"),
                func.sum(
                    func.abs(TransactionSplit.betrag_anteil) * AllocationKeyPosition.prozent / 100
                ).label("brutto_summe"),
            )
            .select_from(Transaction)
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .join(CostCenter, CostCenter.id == TransactionSplit.cost_center_id)
            .join(
                UmlageSourceScopeCostCenter,
                (UmlageSourceScopeCostCenter.cost_center_id == TransactionSplit.cost_center_id)
                & (
                    UmlageSourceScopeCostCenter.umlage_source_scope_id
                    == position.umlage_source_scope_id
                ),
            )
            .join(
                AllocationKey,
                (AllocationKey.org_id == org_id)
                & (
                    (AllocationKey.id == family_root_id)
                    | (AllocationKey.parent_key_id == family_root_id)
                )
                & (Transaction.datum >= AllocationKey.gueltig_von)
                & (
                    (AllocationKey.gueltig_bis.is_(None))
                    | (Transaction.datum <= AllocationKey.gueltig_bis)
                ),
            )
            .join(
                AllocationKeyPosition,
                (AllocationKeyPosition.allocation_key_id == AllocationKey.id)
                & (
                    AllocationKeyPosition.cost_center_id
                    == position.umlage_ziel_cost_center_id
                ),
            )
            .where(Transaction.org_id == org_id)
            .group_by(TransactionSplit.cost_center_id, CostCenter.code, AllocationKey.name)
            .order_by(CostCenter.code.asc())
        ).all()

        per_kostenstelle = [
            {
                "quell_cc_id": r.quell_cc_id,
                "quell_cc_code": r.quell_cc_code,
                "brutto_summe": float(r.brutto_summe) if r.brutto_summe is not None else 0.0,
            }
            for r in rows
        ]
        brutto_umgelegt = sum(r["brutto_summe"] for r in per_kostenstelle)

        fm = position.funding_measure
        betraege = compute_allocation_betraege(
            brutto=brutto_umgelegt,
            foerderquote=float(fm.foerderquote),
            mwst_foerderfahig=fm.mwst_foerderfahig,
            mwst_satz=float(fm.mwst_satz_prozent),
        )

        cap = float(position.betrag_bewilligt)
        ist_nach_cap = min(max(0.0, betraege.betrag_foerderfahig), cap)
        cap_erreicht = betraege.betrag_foerderfahig >= cap - 0.005

        dd_warnings = check_pauschale_doppelfoerderung(
            self.db,
            org_id,
            position.id,
            position.umlage_allocation_key_id,
            position.umlage_ziel_cost_center_id,
            position.umlage_source_scope_id,
        )

        return {
            "data": {
                "position": {
                    "id": position.id,
                    "positionscode": position.positionscode,
                    "bezeichnung": position.bezeichnung,
                    "betrag_bewilligt": cap,
                },
                "schluessel": {
                    "id": ak.id,
                    "name": ak.name,
                    "gueltig_von": ak.gueltig_von.isoformat(),
                    "gueltig_bis": ak.gueltig_bis.isoformat() if ak.gueltig_bis else None,
                    "parent_key_id": ak.parent_key_id,
                },
                "ziel_kostenstelle": {
                    "id": ziel.id,
                    "code": ziel.code,
                    "name": ziel.name,
                    "anteil_prozent": anteil_prozent,
                },
                "quell_pool": {
                    "id": scope.id,
                    "name": scope.name,
                    "beschreibung": scope.beschreibung,
                    "cost_centers": quell_ksts,
                    "cost_center_ids": quell_ids,
                },
                "berechnung": {
                    "per_kostenstelle": per_kostenstelle,
                    "brutto_umgelegt": brutto_umgelegt,
                    "anteil_prozent": anteil_prozent,
                    "foerderquote": float(fm.foerderquote),
                    "mwst_foerderfahig": fm.mwst_foerderfahig,
                    "mwst_satz_prozent": float(fm.mwst_satz_prozent),
                    "betrag_foerderfahig": betraege.betrag_foerderfahig,
                    "betrag_foerderung": betraege.betrag_foerderung,
                    "betrag_eigenanteil": betraege.betrag_eigenanteil,
                    "cap_bewilligt": cap,
                    "ist_nach_cap": ist_nach_cap,
                    "cap_erreicht": cap_erreicht,
                },
                "doppelfoerderung_warnings": format_doppelfoerderung_warnings(dd_warnings),
            }
        }
