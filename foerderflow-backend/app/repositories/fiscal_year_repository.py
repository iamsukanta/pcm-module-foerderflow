"""Data access for FiscalYear (Haushaltsjahre)."""

from __future__ import annotations

from sqlalchemy import select

from app.models.enums import FiscalYearStatus
from app.models.master import FiscalYear
from app.repositories.base import OrgScopedRepository


class FiscalYearRepository(OrgScopedRepository[FiscalYear]):
    model = FiscalYear

    def list_desc(self, org_id: str) -> list[FiscalYear]:
        return list(
            self.db.execute(
                select(FiscalYear)
                .where(FiscalYear.org_id == org_id)
                .order_by(FiscalYear.jahr.desc())
            )
            .scalars()
            .all()
        )

    def get_by_jahr(self, org_id: str, jahr: int) -> FiscalYear | None:
        return self.db.execute(
            select(FiscalYear).where(
                FiscalYear.org_id == org_id, FiscalYear.jahr == jahr
            )
        ).scalar_one_or_none()

    def first_open(self, org_id: str) -> FiscalYear | None:
        return self.db.execute(
            select(FiscalYear).where(
                FiscalYear.org_id == org_id,
                FiscalYear.status == FiscalYearStatus.OFFEN,
            )
        ).scalar_one_or_none()
