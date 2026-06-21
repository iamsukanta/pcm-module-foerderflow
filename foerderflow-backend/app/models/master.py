"""Org master data: CostCenter (cost_centers), Funder (funders),
FunderNachweisFrist (funder_nachweis_fristen), FiscalYear (fiscal_years),
Kostenbereich (kostenbereiche)."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import (
    CostCenterTyp,
    FiscalYearStatus,
    FristBezug,
    FunderTyp,
    VerwendungsnachweisTyp,
)

if TYPE_CHECKING:
    from app.models.funding import FundingMeasure, FundingMeasureCostCenter
    from app.models.organization import Organization


class CostCenter(Base):
    __tablename__ = "cost_centers"
    __table_args__ = (
        UniqueConstraint("org_id", "code"),
        Index("ix_cost_centers_org_id", "org_id"),
        Index("ix_cost_centers_org_id_ist_aktiv", "org_id", "ist_aktiv"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    typ: Mapped[CostCenterTyp] = mapped_column(pg_enum(CostCenterTyp), nullable=False)
    ist_aktiv: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="cost_centers")
    parent: Mapped[CostCenter | None] = relationship(
        remote_side="CostCenter.id", back_populates="children"
    )
    children: Mapped[list[CostCenter]] = relationship(back_populates="parent")
    funding_measure_cost_centers: Mapped[list[FundingMeasureCostCenter]] = relationship(
        back_populates="cost_center"
    )


class Funder(Base):
    __tablename__ = "funders"
    __table_args__ = (
        Index("ix_funders_org_id", "org_id"),
        Index("ix_funders_org_id_typ", "org_id", "typ"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    typ: Mapped[FunderTyp] = mapped_column(pg_enum(FunderTyp), nullable=False)
    notizen: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="funders")
    funding_measures: Mapped[list[FundingMeasure]] = relationship(
        back_populates="funder"
    )
    nachweis_fristen: Mapped[list[FunderNachweisFrist]] = relationship(
        back_populates="funder", cascade="all, delete-orphan"
    )


class FunderNachweisFrist(Base):
    __tablename__ = "funder_nachweis_fristen"
    __table_args__ = (
        UniqueConstraint("org_id", "funder_id", "nachweis_typ"),
        Index("ix_funder_nachweis_fristen_org_id_funder_id", "org_id", "funder_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funder_id: Mapped[str] = mapped_column(
        ForeignKey("funders.id", ondelete="CASCADE"), nullable=False
    )
    nachweis_typ: Mapped[VerwendungsnachweisTyp] = mapped_column(
        pg_enum(VerwendungsnachweisTyp), nullable=False
    )
    bezug: Mapped[FristBezug] = mapped_column(pg_enum(FristBezug), nullable=False)
    tage_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(
        back_populates="funder_nachweis_fristen"
    )
    funder: Mapped[Funder] = relationship(back_populates="nachweis_fristen")


class FiscalYear(Base):
    __tablename__ = "fiscal_years"
    __table_args__ = (
        UniqueConstraint("org_id", "jahr"),
        Index("ix_fiscal_years_org_id", "org_id"),
        Index("ix_fiscal_years_org_id_status", "org_id", "status"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    jahr: Mapped[int] = mapped_column(Integer, nullable=False)
    beginn: Mapped[date] = mapped_column(Date, nullable=False)
    ende: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FiscalYearStatus] = mapped_column(
        pg_enum(FiscalYearStatus), default=FiscalYearStatus.OFFEN, server_default="OFFEN"
    )
    geschlossen_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    geschlossen_von: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="fiscal_years")


class Kostenbereich(Base):
    __tablename__ = "kostenbereiche"
    __table_args__ = (
        Index("ix_kostenbereiche_parent_id", "parent_id"),
        Index("ix_kostenbereiche_org_id", "org_id"),
        Index("ix_kostenbereiche_ist_aktiv", "ist_aktiv"),
    )

    id: Mapped[str] = cuid_pk()
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    bezeichnung: Mapped[str] = mapped_column(String(200), nullable=False)
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("kostenbereiche.id", ondelete="RESTRICT"), nullable=True
    )
    org_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    ist_aktiv: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    skr42_konto_von: Mapped[str | None] = mapped_column(String(20), nullable=True)
    skr42_konto_bis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ist_personal: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    ist_gemeinkosten: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    belegpflicht_default: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    foerderfahig_default: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization | None] = relationship(
        back_populates="kostenbereiche"
    )
    parent: Mapped[Kostenbereich | None] = relationship(
        remote_side="Kostenbereich.id", back_populates="kinder"
    )
    kinder: Mapped[list[Kostenbereich]] = relationship(back_populates="parent")
