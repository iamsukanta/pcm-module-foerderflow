"""Generic org-scoped repository base.

Every domain table carries `org_id`; the repository layer guarantees row-level
tenant isolation (the monolith filters every query by the session org). Repositories
hold *data access only* — business rules live in services/use_cases.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class OrgScopedRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, org_id: str, id_: str) -> ModelT | None:
        return self.db.execute(
            select(self.model).where(
                self.model.id == id_, self.model.org_id == org_id  # type: ignore[attr-defined]
            )
        ).scalar_one_or_none()

    def list(self, org_id: str) -> list[ModelT]:
        return list(
            self.db.execute(
                select(self.model).where(self.model.org_id == org_id)  # type: ignore[attr-defined]
            )
            .scalars()
            .all()
        )

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj
