"""Organization — tenant root. 1:1 port of Prisma `Organization` (organizations)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import Rechtsform

if TYPE_CHECKING:
    from app.models.allocation import AllocationKey, UmlageSourceScope
    from app.models.auth import OrganizationMembership, OrgInvite
    from app.models.booking_rule import BookingRule, BookingRuleApplication
    from app.models.finanzplan import (
        FinanzplanPosition,
        HaushaltsPlanPosten,
        VerwNachweis,
    )
    from app.models.funding import (
        BescheidDokument,
        Funder,
        FunderNachweisFrist,
        FundingMeasure,
        NachweisTemplate,
    )
    from app.models.master import CostCenter, FiscalYear, Kostenbereich
    from app.models.mittelabruf import Mittelabruf
    from app.models.payroll import Employee, EmployerGrossFactor, MonthlyPayroll
    from app.models.transaction import (
        BankAccount,
        CsvImportProfile,
        ImportBatch,
        Transaction,
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = cuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    rechtsform: Mapped[Rechtsform] = mapped_column(pg_enum(Rechtsform), nullable=False)
    # Vertraglich vereinbarte Wochenstunden (Vollzeit) — Basis für VZÄ-Berechnungen
    regelarbeitszeit_stunden: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False
    )
    # Module PCM: org-weiter BAV-Satz (Default-Fallback, wenn die Tarif-Zeile
    # keinen eigenen bav_rate_pct trägt). 0 = keine BAV per Default.
    bav_rate_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal(0), server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    # Relations
    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    invites: Mapped[list[OrgInvite]] = relationship(back_populates="organization")
    cost_centers: Mapped[list[CostCenter]] = relationship(back_populates="organization")
    funders: Mapped[list[Funder]] = relationship(back_populates="organization")
    funding_measures: Mapped[list[FundingMeasure]] = relationship(
        back_populates="organization"
    )
    allocation_keys: Mapped[list[AllocationKey]] = relationship(
        back_populates="organization"
    )
    fiscal_years: Mapped[list[FiscalYear]] = relationship(back_populates="organization")
    import_batches: Mapped[list[ImportBatch]] = relationship(
        back_populates="organization"
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="organization"
    )
    bank_accounts: Mapped[list[BankAccount]] = relationship(
        back_populates="organization"
    )
    csv_import_profiles: Mapped[list[CsvImportProfile]] = relationship(
        back_populates="organization"
    )
    nachweis_templates: Mapped[list[NachweisTemplate]] = relationship(
        back_populates="organization"
    )
    employees: Mapped[list[Employee]] = relationship(back_populates="organization")
    employer_gross_factors: Mapped[list[EmployerGrossFactor]] = relationship(
        back_populates="organization"
    )
    monthly_payrolls: Mapped[list[MonthlyPayroll]] = relationship(
        back_populates="organization"
    )
    mittelabrufe: Mapped[list[Mittelabruf]] = relationship(
        back_populates="organization"
    )
    booking_rules: Mapped[list[BookingRule]] = relationship(back_populates="org")
    booking_rule_applications: Mapped[list[BookingRuleApplication]] = relationship(
        back_populates="org"
    )
    finanzplan_positionen: Mapped[list[FinanzplanPosition]] = relationship(
        back_populates="organization"
    )
    haushaltsplan_posten: Mapped[list[HaushaltsPlanPosten]] = relationship(
        back_populates="organization"
    )
    verwendungsnachweise: Mapped[list[VerwNachweis]] = relationship(
        back_populates="organization"
    )
    funder_nachweis_fristen: Mapped[list[FunderNachweisFrist]] = relationship(
        back_populates="organization"
    )
    bescheid_dokumente: Mapped[list[BescheidDokument]] = relationship(
        back_populates="organization"
    )
    kostenbereiche: Mapped[list[Kostenbereich]] = relationship(
        back_populates="organization"
    )
    umlage_source_scopes: Mapped[list[UmlageSourceScope]] = relationship(
        back_populates="organization"
    )
