"""Funding measures: FundingMeasure (funding_measures), BescheidDokument
(bescheid_dokumente), FundingRule (funding_rules), FundingMeasureCostCenter
(funding_measure_cost_centers), NachweisTemplate (nachweis_templates).

NOTE on org_id: Prisma only creates an FK where an `@relation` exists. FundingRule
and FundingMeasureCostCenter carry org_id as a *denormalized* column (no relation),
so those are plain String columns here — faithfully (no FK)."""

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
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import JSONBType, created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import (
    BescheidQuelle,
    EigenanteilTyp,
    FinanzierungsartTyp,
    FundingMeasureStatus,
    FundingRuleTyp,
    MittelabrufVerfahren,
)

if TYPE_CHECKING:
    from app.models.booking_rule import BookingRule, BookingRuleSplit
    from app.models.finanzplan import (
        FinanzplanPosition,
        HaushaltsPlanPosten,
        VerwNachweis,
    )
    from app.models.master import CostCenter, Funder
    from app.models.mittelabruf import Mittelabruf
    from app.models.organization import Organization
    from app.models.transaction import FundAllocation


class FundingMeasure(Base):
    __tablename__ = "funding_measures"
    __table_args__ = (
        Index("ix_funding_measures_org_id", "org_id"),
        Index("ix_funding_measures_org_id_status", "org_id", "status"),
        Index("ix_funding_measures_org_id_funder_id", "org_id", "funder_id"),
        Index("ix_funding_measures_org_id_laufzeit_bis", "org_id", "laufzeit_bis"),
        Index(
            "ix_funding_measures_org_id_foerderkennzeichen",
            "org_id",
            "foerderkennzeichen",
        ),
        Index("ix_funding_measures_org_id_antragsnummer", "org_id", "antragsnummer"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funder_id: Mapped[str] = mapped_column(
        ForeignKey("funders.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)

    budget_gesamt: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    foerderquote: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    laufzeit_von: Mapped[date] = mapped_column(Date, nullable=False)
    laufzeit_bis: Mapped[date] = mapped_column(Date, nullable=False)
    durchfuehrungs_von: Mapped[date | None] = mapped_column(Date, nullable=True)
    durchfuehrungs_bis: Mapped[date | None] = mapped_column(Date, nullable=True)

    antragsnummer: Mapped[str | None] = mapped_column(String(100), nullable=True)

    verwaltungspauschale_erlaubt: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    verwaltungspauschale_prozent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    budget_flexibilitaet_prozent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal(20), server_default="20", nullable=False
    )
    overhead_limit_prozent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    mwst_foerderfahig: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    mwst_satz_prozent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("19.0"), server_default="19.0", nullable=False
    )

    mittelabruf_verfahren: Mapped[MittelabrufVerfahren] = mapped_column(
        pg_enum(MittelabrufVerfahren), nullable=False
    )
    status: Mapped[FundingMeasureStatus] = mapped_column(
        pg_enum(FundingMeasureStatus),
        default=FundingMeasureStatus.AKTIV,
        server_default="AKTIV",
    )

    foerderkennzeichen: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finanzierungsart: Mapped[FinanzierungsartTyp | None] = mapped_column(
        pg_enum(FinanzierungsartTyp), nullable=True
    )
    eigenanteil_typ: Mapped[EigenanteilTyp | None] = mapped_column(
        pg_enum(EigenanteilTyp), nullable=True
    )
    eigenmittel_betrag: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    drittmittel_betrag: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    # ── Module PCM ──────────────────────────────────────────────────
    # Gates allocation_method = PLAN_PERCENTAGE on linked salary assignments.
    # Additive nullable-default column; existing rows default to false (= the
    # §4 ANBest-P actual-hours rule applies unless the funder explicitly allows
    # plan-based allocation).
    allows_plan_based_allocation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="funding_measures")
    funder: Mapped[Funder] = relationship(back_populates="funding_measures")
    rules: Mapped[list[FundingRule]] = relationship(
        back_populates="funding_measure", cascade="all, delete-orphan"
    )
    cost_centers: Mapped[list[FundingMeasureCostCenter]] = relationship(
        back_populates="funding_measure", cascade="all, delete-orphan"
    )
    fund_allocations: Mapped[list[FundAllocation]] = relationship(
        back_populates="funding_measure"
    )
    nachweis_template: Mapped[NachweisTemplate | None] = relationship(
        back_populates="funding_measure", uselist=False
    )
    mittelabrufe: Mapped[list[Mittelabruf]] = relationship(
        back_populates="funding_measure"
    )
    booking_rules: Mapped[list[BookingRule]] = relationship(
        back_populates="funding_measure"
    )
    booking_rule_splits: Mapped[list[BookingRuleSplit]] = relationship(
        back_populates="funding_measure"
    )
    finanzplan_positionen: Mapped[list[FinanzplanPosition]] = relationship(
        back_populates="funding_measure", cascade="all, delete-orphan"
    )
    haushaltsplan_posten: Mapped[list[HaushaltsPlanPosten]] = relationship(
        back_populates="funding_measure", cascade="all, delete-orphan"
    )
    verwendungsnachweise: Mapped[list[VerwNachweis]] = relationship(
        back_populates="funding_measure"
    )
    bescheid_dokument: Mapped[BescheidDokument | None] = relationship(
        back_populates="funding_measure", uselist=False
    )


class BescheidDokument(Base):
    __tablename__ = "bescheid_dokumente"
    __table_args__ = (Index("ix_bescheid_dokumente_org_id", "org_id"),)

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    quelle: Mapped[BescheidQuelle] = mapped_column(
        pg_enum(BescheidQuelle),
        default=BescheidQuelle.MANUAL_UPLOAD,
        server_default="MANUAL_UPLOAD",
    )

    organization: Mapped[Organization] = relationship(
        back_populates="bescheid_dokumente"
    )
    funding_measure: Mapped[FundingMeasure] = relationship(
        back_populates="bescheid_dokument"
    )


class FundingRule(Base):
    __tablename__ = "funding_rules"
    __table_args__ = (
        Index("ix_funding_rules_org_id", "org_id"),
        Index("ix_funding_rules_funding_measure_id", "funding_measure_id"),
        Index("ix_funding_rules_funding_measure_id_typ", "funding_measure_id", "typ"),
    )

    id: Mapped[str] = cuid_pk()
    # denormalized; no FK in Prisma (no organization relation on FundingRule)
    org_id: Mapped[str] = mapped_column(String, nullable=False)
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="CASCADE"), nullable=False
    )
    typ: Mapped[FundingRuleTyp] = mapped_column(pg_enum(FundingRuleTyp), nullable=False)
    schluessel: Mapped[str] = mapped_column(String, nullable=False)
    wert: Mapped[str | None] = mapped_column(Text, nullable=True)
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    funding_measure: Mapped[FundingMeasure] = relationship(back_populates="rules")


class FundingMeasureCostCenter(Base):
    __tablename__ = "funding_measure_cost_centers"
    __table_args__ = (
        UniqueConstraint("funding_measure_id", "cost_center_id"),
        Index("ix_funding_measure_cost_centers_org_id", "org_id"),
        Index(
            "ix_funding_measure_cost_centers_funding_measure_id", "funding_measure_id"
        ),
        Index("ix_funding_measure_cost_centers_cost_center_id", "cost_center_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = created_at()

    funding_measure: Mapped[FundingMeasure] = relationship(back_populates="cost_centers")
    cost_center: Mapped[CostCenter] = relationship(
        back_populates="funding_measure_cost_centers"
    )


class NachweisTemplate(Base):
    __tablename__ = "nachweis_templates"
    __table_args__ = (Index("ix_nachweis_templates_org_id", "org_id"),)

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    programm_typ: Mapped[str] = mapped_column(String(100), nullable=False)
    datei_pfad: Mapped[str] = mapped_column(String(500), nullable=False)
    datei_name: Mapped[str] = mapped_column(String(255), nullable=False)
    datei_typ: Mapped[str] = mapped_column(String(50), nullable=False)
    feld_mappings: Mapped[dict] = mapped_column(
        JSONBType, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(
        back_populates="nachweis_templates"
    )
    funding_measure: Mapped[FundingMeasure] = relationship(
        back_populates="nachweis_template"
    )
