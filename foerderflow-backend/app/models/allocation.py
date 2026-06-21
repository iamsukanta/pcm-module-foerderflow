"""Allocation / distribution: AllocationKey (allocation_keys), AllocationKeyPosition
(allocation_key_positions), UmlageSourceScope (umlage_source_scopes),
UmlageSourceScopeCostCenter (umlage_source_scope_cost_centers).

INVARIANT (app-enforced): sum(AllocationKeyPosition.prozent) per key == 100.000."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import AllocationBasis

if TYPE_CHECKING:
    from app.models.master import CostCenter
    from app.models.organization import Organization


class AllocationKey(Base):
    __tablename__ = "allocation_keys"
    __table_args__ = (
        Index("ix_allocation_keys_org_id", "org_id"),
        Index("ix_allocation_keys_org_id_ist_aktiv", "org_id", "ist_aktiv"),
        Index(
            "ix_allocation_keys_org_id_gueltig_von_gueltig_bis",
            "org_id",
            "gueltig_von",
            "gueltig_bis",
        ),
        Index("ix_allocation_keys_parent_key_id", "parent_key_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    basis: Mapped[AllocationBasis] = mapped_column(
        pg_enum(AllocationBasis), nullable=False
    )
    gueltig_von: Mapped[date] = mapped_column(Date, nullable=False)
    gueltig_bis: Mapped[date | None] = mapped_column(Date, nullable=True)
    ist_aktiv: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    parent_key_id: Mapped[str | None] = mapped_column(
        ForeignKey("allocation_keys.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="allocation_keys")
    positions: Mapped[list[AllocationKeyPosition]] = relationship(
        back_populates="allocation_key", cascade="all, delete-orphan"
    )
    parent_key: Mapped[AllocationKey | None] = relationship(
        remote_side="AllocationKey.id", back_populates="versions"
    )
    versions: Mapped[list[AllocationKey]] = relationship(back_populates="parent_key")


class AllocationKeyPosition(Base):
    __tablename__ = "allocation_key_positions"
    __table_args__ = (
        UniqueConstraint("allocation_key_id", "cost_center_id"),
        Index("ix_allocation_key_positions_org_id", "org_id"),
        Index("ix_allocation_key_positions_allocation_key_id", "allocation_key_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    allocation_key_id: Mapped[str] = mapped_column(
        ForeignKey("allocation_keys.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=False
    )
    prozent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)

    allocation_key: Mapped[AllocationKey] = relationship(back_populates="positions")
    cost_center: Mapped[CostCenter] = relationship()


class UmlageSourceScope(Base):
    __tablename__ = "umlage_source_scopes"
    __table_args__ = (
        UniqueConstraint("org_id", "name"),
        Index("ix_umlage_source_scopes_org_id", "org_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(
        back_populates="umlage_source_scopes"
    )
    cost_centers: Mapped[list[UmlageSourceScopeCostCenter]] = relationship(
        back_populates="umlage_source_scope", cascade="all, delete-orphan"
    )


class UmlageSourceScopeCostCenter(Base):
    __tablename__ = "umlage_source_scope_cost_centers"
    __table_args__ = (
        UniqueConstraint("umlage_source_scope_id", "cost_center_id"),
        Index("ix_umlage_source_scope_cost_centers_org_id", "org_id"),
        Index(
            "ix_umlage_source_scope_cost_centers_cost_center_id", "cost_center_id"
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    umlage_source_scope_id: Mapped[str] = mapped_column(
        ForeignKey("umlage_source_scopes.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=False
    )

    umlage_source_scope: Mapped[UmlageSourceScope] = relationship(
        back_populates="cost_centers"
    )
    cost_center: Mapped[CostCenter] = relationship()
