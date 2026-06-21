"""Data access for CostCenter (Kostenstellen)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.funding import FundingMeasureCostCenter
from app.models.master import CostCenter
from app.repositories.base import OrgScopedRepository


class CostCenterRepository(OrgScopedRepository[CostCenter]):
    model = CostCenter

    def list_with_relations(
        self, org_id: str, include_inactive: bool
    ) -> list[CostCenter]:
        stmt = (
            select(CostCenter)
            .where(CostCenter.org_id == org_id)
            .options(selectinload(CostCenter.parent), selectinload(CostCenter.children))
            .order_by(CostCenter.name.asc())
        )
        if not include_inactive:
            stmt = stmt.where(CostCenter.ist_aktiv.is_(True))
        return list(self.db.execute(stmt).scalars().all())

    def get_with_relations(self, org_id: str, id_: str) -> CostCenter | None:
        return self.db.execute(
            select(CostCenter)
            .where(CostCenter.id == id_, CostCenter.org_id == org_id)
            .options(
                selectinload(CostCenter.parent),
                selectinload(CostCenter.children),
                selectinload(CostCenter.funding_measure_cost_centers).selectinload(
                    FundingMeasureCostCenter.funding_measure
                ),
            )
        ).scalar_one_or_none()

    def get_by_code(
        self, org_id: str, code: str, exclude_id: str | None = None
    ) -> CostCenter | None:
        stmt = select(CostCenter).where(
            CostCenter.org_id == org_id, CostCenter.code == code
        )
        if exclude_id is not None:
            stmt = stmt.where(CostCenter.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def funding_measure_counts(self, cost_center_ids: list[str]) -> dict[str, int]:
        """Return {cost_center_id: count of linked funding measures} in one query
        (the monolith's `_count.funding_measure_cost_centers`)."""
        if not cost_center_ids:
            return {}
        rows = self.db.execute(
            select(
                FundingMeasureCostCenter.cost_center_id,
                func.count(FundingMeasureCostCenter.id),
            )
            .where(FundingMeasureCostCenter.cost_center_id.in_(cost_center_ids))
            .group_by(FundingMeasureCostCenter.cost_center_id)
        ).all()
        return {cc_id: n for cc_id, n in rows}

    def active_children(self, org_id: str, parent_id: str) -> list[CostCenter]:
        return list(
            self.db.execute(
                select(CostCenter)
                .where(
                    CostCenter.org_id == org_id,
                    CostCenter.parent_id == parent_id,
                    CostCenter.ist_aktiv.is_(True),
                )
                .order_by(CostCenter.name.asc())
            )
            .scalars()
            .all()
        )

    def deactivate_children(self, org_id: str, parent_id: str) -> None:
        for child in self.active_children(org_id, parent_id):
            child.ist_aktiv = False
