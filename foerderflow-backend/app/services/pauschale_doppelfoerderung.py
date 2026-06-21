"""Doppelförderungs-Soft-Check — port of lib/pauschale-doppelfoerderung.ts.

For UMLAGE_KOSTENSTELLEN pauschale positions: if two measures umlage the same
source cost-centers and their combined measure-shares exceed 100%, the same booked
euro could be reported to multiple funders (ANBest-P double-funding). Returns
soft warnings (never a hard block).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from app.models.allocation import (
    AllocationKeyPosition,
    UmlageSourceScope,
    UmlageSourceScopeCostCenter,
)
from app.models.enums import PauschaleTyp
from app.models.finanzplan import FinanzplanPosition


def _key_prozent(db: Session, allocation_key_id: str, cost_center_id: str) -> float | None:
    row = db.execute(
        select(AllocationKeyPosition.prozent).where(
            AllocationKeyPosition.allocation_key_id == allocation_key_id,
            AllocationKeyPosition.cost_center_id == cost_center_id,
        )
    ).scalar_one_or_none()
    return float(row) if row is not None else None


def check_pauschale_doppelfoerderung(
    db: Session,
    org_id: str,
    position_id_excluded: str | None,
    umlage_allocation_key_id: str,
    umlage_ziel_cost_center_id: str,
    umlage_source_scope_id: str,
) -> list[dict[str, Any]]:
    eigen_prozent = _key_prozent(db, umlage_allocation_key_id, umlage_ziel_cost_center_id)
    if eigen_prozent is None:
        return []

    eigen_scope = (
        db.execute(
            select(UmlageSourceScopeCostCenter)
            .where(
                UmlageSourceScopeCostCenter.umlage_source_scope_id == umlage_source_scope_id,
                UmlageSourceScopeCostCenter.org_id == org_id,
            )
            .options(selectinload(UmlageSourceScopeCostCenter.cost_center))
        )
        .scalars()
        .all()
    )
    if not eigen_scope:
        return []

    andere_stmt = (
        select(FinanzplanPosition)
        .where(
            FinanzplanPosition.org_id == org_id,
            FinanzplanPosition.pauschale_typ == PauschaleTyp.UMLAGE_KOSTENSTELLEN,
            FinanzplanPosition.ist_pauschale.is_(True),
            FinanzplanPosition.umlage_source_scope_id.is_not(None),
        )
        .options(
            selectinload(FinanzplanPosition.umlage_source_scope).selectinload(
                UmlageSourceScope.cost_centers
            ),
            selectinload(FinanzplanPosition.umlage_ziel_cost_center),
            selectinload(FinanzplanPosition.funding_measure),
        )
    )
    if position_id_excluded:
        andere_stmt = andere_stmt.where(FinanzplanPosition.id != position_id_excluded)
    andere = db.execute(andere_stmt).scalars().all()

    warnings: list[dict[str, Any]] = []
    for eigen_kst in eigen_scope:
        kollidierende: list[dict[str, Any]] = []
        for ap in andere:
            fremd_quell_ids = (
                [c.cost_center_id for c in ap.umlage_source_scope.cost_centers]
                if ap.umlage_source_scope
                else []
            )
            if eigen_kst.cost_center_id not in fremd_quell_ids:
                continue
            if not ap.umlage_allocation_key_id or not ap.umlage_ziel_cost_center_id:
                continue
            fremd_prozent = _key_prozent(
                db, ap.umlage_allocation_key_id, ap.umlage_ziel_cost_center_id
            )
            if fremd_prozent is None:
                continue
            kollidierende.append(
                {
                    "position_id": ap.id,
                    "positionscode": ap.positionscode,
                    "bezeichnung": ap.bezeichnung,
                    "funding_measure_name": ap.funding_measure.name,
                    "ziel_cost_center_code": (
                        ap.umlage_ziel_cost_center.code
                        if ap.umlage_ziel_cost_center
                        else "?"
                    ),
                    "prozent": fremd_prozent,
                }
            )
        fremd_summe = sum(k["prozent"] for k in kollidierende)
        gesamt = eigen_prozent + fremd_summe
        if gesamt > 100:
            warnings.append(
                {
                    "quell_cost_center_code": eigen_kst.cost_center.code,
                    "quell_cost_center_id": eigen_kst.cost_center_id,
                    "eigen_prozent": eigen_prozent,
                    "fremd_prozent": fremd_summe,
                    "summe_prozent": gesamt,
                    "kollidierende_positionen": kollidierende,
                }
            )
    return warnings


def format_doppelfoerderung_warnings(warnings: list[dict[str, Any]]) -> list[str]:
    out = []
    for w in warnings:
        koll = ", ".join(
            f'„{k["positionscode"]} {k["bezeichnung"]}" ({k["funding_measure_name"]}, '
            f'{k["ziel_cost_center_code"]}: {k["prozent"]}%)'
            for k in w["kollidierende_positionen"]
        )
        out.append(
            f'Quell-KST {w["quell_cost_center_code"]}: eigener Anteil '
            f'{w["eigen_prozent"]}% + bestehende {w["fremd_prozent"]}% = '
            f'{w["summe_prozent"]}% > 100% — Doppelförderungs-Risiko mit {koll}'
        )
    return out
