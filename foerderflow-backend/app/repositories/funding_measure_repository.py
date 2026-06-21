"""Data access for FundingMeasure (Fördermassnahmen)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.funding import FundingMeasure, FundingMeasureCostCenter, FundingRule
from app.models.master import CostCenter
from app.models.mittelabruf import Mittelabruf
from app.models.transaction import FundAllocation
from app.repositories.base import OrgScopedRepository


class FundingMeasureRepository(OrgScopedRepository[FundingMeasure]):
    model = FundingMeasure

    def list_filtered(
        self, org_id: str, status: str | None, funder_id: str | None
    ) -> list[FundingMeasure]:
        stmt = (
            select(FundingMeasure)
            .where(FundingMeasure.org_id == org_id)
            .options(
                selectinload(FundingMeasure.funder),
                selectinload(FundingMeasure.cost_centers),
                selectinload(FundingMeasure.rules),
            )
            .order_by(
                FundingMeasure.status.asc(),
                FundingMeasure.laufzeit_bis.asc(),
                FundingMeasure.name.asc(),
            )
        )
        if status:
            stmt = stmt.where(FundingMeasure.status == status)
        if funder_id:
            stmt = stmt.where(FundingMeasure.funder_id == funder_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_full(self, org_id: str, id_: str) -> FundingMeasure | None:
        return self.db.execute(
            select(FundingMeasure)
            .where(FundingMeasure.id == id_, FundingMeasure.org_id == org_id)
            .options(
                selectinload(FundingMeasure.funder),
                selectinload(FundingMeasure.rules),
                selectinload(FundingMeasure.cost_centers).selectinload(
                    FundingMeasureCostCenter.cost_center
                ),
            )
        ).scalar_one_or_none()

    def get_plain(self, org_id: str, id_: str) -> FundingMeasure | None:
        return self.get(org_id, id_)

    def cost_center_ids_existing(self, org_id: str, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        rows = self.db.execute(
            select(CostCenter.id).where(
                CostCenter.id.in_(ids), CostCenter.org_id == org_id
            )
        ).all()
        return {r[0] for r in rows}

    def replace_rules(self, org_id: str, measure_id: str, rules: list[dict]) -> None:
        self.db.query(FundingRule).filter(
            FundingRule.funding_measure_id == measure_id
        ).delete(synchronize_session=False)
        for r in rules:
            self.db.add(
                FundingRule(
                    org_id=org_id,
                    funding_measure_id=measure_id,
                    typ=r["typ"],
                    schluessel=r["schluessel"],
                    wert=r.get("wert"),
                    beschreibung=r.get("beschreibung"),
                )
            )

    def replace_cost_centers(
        self, org_id: str, measure_id: str, cost_center_ids: list[str]
    ) -> None:
        self.db.query(FundingMeasureCostCenter).filter(
            FundingMeasureCostCenter.funding_measure_id == measure_id
        ).delete(synchronize_session=False)
        for cc_id in dict.fromkeys(cost_center_ids):  # skipDuplicates
            self.db.add(
                FundingMeasureCostCenter(
                    org_id=org_id,
                    funding_measure_id=measure_id,
                    cost_center_id=cc_id,
                )
            )

    def fund_allocation_count(self, measure_id: str) -> int:
        return self.db.execute(
            select(func.count(FundAllocation.id)).where(
                FundAllocation.funding_measure_id == measure_id
            )
        ).scalar_one()

    def mittelabruf_count(self, measure_id: str) -> int:
        return self.db.execute(
            select(func.count(Mittelabruf.id)).where(
                Mittelabruf.funding_measure_id == measure_id
            )
        ).scalar_one()
