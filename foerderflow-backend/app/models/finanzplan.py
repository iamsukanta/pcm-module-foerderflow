"""Finanzplan & Verwendungsnachweis: FinanzplanPosition (finanzplan_positionen),
FinanzplanPositionKostenbereich (finanzplan_position_kostenbereiche),
HaushaltsPlanPosten (haushaltsplan_posten), VerwNachweis (verwendungsnachweise)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import JSONBType, created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import (
    EigenanteilTyp,
    PauschaleTyp,
    VerwendungsnachweisStatus,
    VerwendungsnachweisTyp,
)

if TYPE_CHECKING:
    from app.models.allocation import AllocationKey, UmlageSourceScope
    from app.models.funding import FundingMeasure
    from app.models.master import CostCenter, FiscalYear, Kostenbereich
    from app.models.organization import Organization
    from app.models.transaction import FundAllocation


class FinanzplanPosition(Base):
    __tablename__ = "finanzplan_positionen"
    __table_args__ = (
        UniqueConstraint("funding_measure_id", "positionscode"),
        Index("ix_finanzplan_positionen_org_id", "org_id"),
        Index("ix_finanzplan_positionen_funding_measure_id", "funding_measure_id"),
        Index(
            "ix_finanzplan_positionen_org_id_deckungsfaehigkeit_pool",
            "org_id",
            "deckungsfaehigkeit_pool",
        ),
        Index(
            "ix_finanzplan_positionen_umlage_source_scope_id", "umlage_source_scope_id"
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="CASCADE"), nullable=False
    )
    positionscode: Mapped[str] = mapped_column(String(50), nullable=False)
    bezeichnung: Mapped[str] = mapped_column(String(500), nullable=False)
    betrag_bewilligt: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    deckungsfaehigkeit_pool: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    ueberziehung_limit_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal(20), server_default="20", nullable=False
    )
    ueberziehung_genehmigungspflichtig: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    foerderfahigkeit_hinweis: Mapped[str | None] = mapped_column(Text, nullable=True)
    eigenanteil_typ: Mapped[EigenanteilTyp | None] = mapped_column(
        pg_enum(EigenanteilTyp), nullable=True
    )
    ist_pauschale: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    pauschale_typ: Mapped[PauschaleTyp | None] = mapped_column(
        pg_enum(PauschaleTyp), nullable=True
    )
    pauschale_prozent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    umlage_allocation_key_id: Mapped[str | None] = mapped_column(
        ForeignKey("allocation_keys.id", ondelete="RESTRICT"), nullable=True
    )
    umlage_ziel_cost_center_id: Mapped[str | None] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True
    )
    umlage_source_scope_id: Mapped[str | None] = mapped_column(
        ForeignKey("umlage_source_scopes.id", ondelete="RESTRICT"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(
        back_populates="finanzplan_positionen"
    )
    funding_measure: Mapped[FundingMeasure] = relationship(
        back_populates="finanzplan_positionen"
    )
    kostenbereiche: Mapped[list[FinanzplanPositionKostenbereich]] = relationship(
        back_populates="finanzplan_position", cascade="all, delete-orphan"
    )
    haushaltsplan_posten: Mapped[list[HaushaltsPlanPosten]] = relationship(
        back_populates="finanzplan_position", cascade="all, delete-orphan"
    )
    fund_allocations: Mapped[list[FundAllocation]] = relationship(
        back_populates="finanzplan_position"
    )
    umlage_allocation_key: Mapped[AllocationKey | None] = relationship(
        foreign_keys=[umlage_allocation_key_id]
    )
    umlage_ziel_cost_center: Mapped[CostCenter | None] = relationship(
        foreign_keys=[umlage_ziel_cost_center_id]
    )
    umlage_source_scope: Mapped[UmlageSourceScope | None] = relationship(
        foreign_keys=[umlage_source_scope_id]
    )


class FinanzplanPositionKostenbereich(Base):
    __tablename__ = "finanzplan_position_kostenbereiche"
    __table_args__ = (
        UniqueConstraint("finanzplan_position_id", "kostenbereich_id"),
        Index("ix_finanzplan_position_kostenbereiche_org_id", "org_id"),
        Index(
            "ix_finanzplan_position_kostenbereiche_finanzplan_position_id",
            "finanzplan_position_id",
        ),
        Index(
            "ix_finanzplan_position_kostenbereiche_kostenbereich_id", "kostenbereich_id"
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    finanzplan_position_id: Mapped[str] = mapped_column(
        ForeignKey("finanzplan_positionen.id", ondelete="CASCADE"), nullable=False
    )
    kostenbereich_id: Mapped[str] = mapped_column(
        ForeignKey("kostenbereiche.id", ondelete="RESTRICT"), nullable=False
    )
    foerderfahig_anteil: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal(1), server_default="1", nullable=False
    )
    cap_betrag: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    hinweis: Mapped[str | None] = mapped_column(Text, nullable=True)

    finanzplan_position: Mapped[FinanzplanPosition] = relationship(
        back_populates="kostenbereiche"
    )
    kostenbereich: Mapped[Kostenbereich] = relationship()


class HaushaltsPlanPosten(Base):
    __tablename__ = "haushaltsplan_posten"
    __table_args__ = (
        UniqueConstraint(
            "funding_measure_id",
            "finanzplan_position_id",
            "kostenbereich_id",
            "fuer_monat",
        ),
        Index("ix_haushaltsplan_posten_org_id", "org_id"),
        Index("ix_haushaltsplan_posten_funding_measure_id", "funding_measure_id"),
        Index("ix_haushaltsplan_posten_finanzplan_position_id", "finanzplan_position_id"),
        Index("ix_haushaltsplan_posten_org_id_fuer_monat", "org_id", "fuer_monat"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="CASCADE"), nullable=False
    )
    finanzplan_position_id: Mapped[str] = mapped_column(
        ForeignKey("finanzplan_positionen.id", ondelete="CASCADE"), nullable=False
    )
    kostenbereich_id: Mapped[str] = mapped_column(
        ForeignKey("kostenbereiche.id", ondelete="RESTRICT"), nullable=False
    )
    fuer_monat: Mapped[date] = mapped_column(Date, nullable=False)
    betrag_geplant: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quelle: Mapped[str] = mapped_column(
        String(50), default="MANUELL", server_default="MANUELL", nullable=False
    )
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(
        back_populates="haushaltsplan_posten"
    )
    funding_measure: Mapped[FundingMeasure] = relationship(
        back_populates="haushaltsplan_posten"
    )
    finanzplan_position: Mapped[FinanzplanPosition] = relationship(
        back_populates="haushaltsplan_posten"
    )
    kostenbereich: Mapped[Kostenbereich] = relationship()


class VerwNachweis(Base):
    __tablename__ = "verwendungsnachweise"
    __table_args__ = (
        Index("ix_verwendungsnachweise_org_id", "org_id"),
        Index(
            "ix_verwendungsnachweise_org_id_funding_measure_id",
            "org_id",
            "funding_measure_id",
        ),
        Index("ix_verwendungsnachweise_org_id_status", "org_id", "status"),
        Index("ix_verwendungsnachweise_frist", "frist"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="RESTRICT"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False
    )
    zeitraum_von: Mapped[date] = mapped_column(Date, nullable=False)
    zeitraum_bis: Mapped[date] = mapped_column(Date, nullable=False)
    frist: Mapped[date] = mapped_column(Date, nullable=False)
    typ: Mapped[VerwendungsnachweisTyp] = mapped_column(
        pg_enum(VerwendungsnachweisTyp), nullable=False
    )
    status: Mapped[VerwendungsnachweisStatus] = mapped_column(
        pg_enum(VerwendungsnachweisStatus),
        default=VerwendungsnachweisStatus.OFFEN,
        server_default="OFFEN",
    )
    snapshot_json: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    eingereicht_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    eingereicht_von: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(
        back_populates="verwendungsnachweise"
    )
    funding_measure: Mapped[FundingMeasure] = relationship(
        back_populates="verwendungsnachweise"
    )
    fiscal_year: Mapped[FiscalYear] = relationship()
