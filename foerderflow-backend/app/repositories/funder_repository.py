"""Data access for Funder (Fördergeber)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.funding import FundingMeasure
from app.models.master import Funder
from app.repositories.base import OrgScopedRepository


class FunderRepository(OrgScopedRepository[Funder]):
    model = Funder

    def list_ordered(self, org_id: str) -> list[Funder]:
        return list(
            self.db.execute(
                select(Funder).where(Funder.org_id == org_id).order_by(Funder.name.asc())
            )
            .scalars()
            .all()
        )

    def get_with_measures(self, org_id: str, id_: str) -> Funder | None:
        return self.db.execute(
            select(Funder)
            .where(Funder.id == id_, Funder.org_id == org_id)
            .options(selectinload(Funder.funding_measures))
        ).scalar_one_or_none()

    def measure_counts(self, funder_ids: list[str]) -> dict[str, int]:
        if not funder_ids:
            return {}
        rows = self.db.execute(
            select(FundingMeasure.funder_id, func.count(FundingMeasure.id))
            .where(FundingMeasure.funder_id.in_(funder_ids))
            .group_by(FundingMeasure.funder_id)
        ).all()
        return {fid: n for fid, n in rows}

    def measure_count(self, funder_id: str) -> int:
        return self.db.execute(
            select(func.count(FundingMeasure.id)).where(
                FundingMeasure.funder_id == funder_id
            )
        ).scalar_one()
