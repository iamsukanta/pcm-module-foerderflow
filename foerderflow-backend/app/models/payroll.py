"""Payroll / HR: Employee (employees), EmployeeContract (employee_contracts),
SalaryComponent (salary_components), EmployerGrossFactor (employer_gross_factors),
TarifTabelle (tarif_tabelle), MonthlyPayroll (monthly_payrolls), PayrollComponent
(payroll_components), PayrollAllocation (payroll_allocations).

Payroll formula (preserved verbatim from the monolith):
  actual_salary = base_salary × (assigned_hours / standard_hours)
  an_brutto     = actual_salary + Σ(components where nach_multiplikator = false)
  ag_brutto     = an_brutto × ag_faktor + Σ(components where nach_multiplikator = true)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
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
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import (
    AllocationMethod,
    AllocationOrigin,
    EmployeeType,
    PayrollStatus,
    SalaryComponentTyp,
    Tarifwerk,
    Vertragsart,
)

if TYPE_CHECKING:
    from app.models.allocation import AllocationKey
    from app.models.finanzplan import FinanzplanPosition
    from app.models.funding import FundingMeasure
    from app.models.master import CostCenter, FiscalYear
    from app.models.organization import Organization
    from app.models.pcm_payroll import PayrollDetailLine
    from app.models.pcm_tariff import SalaryTariff


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("org_id", "employee_code"),
        Index("ix_employees_org_id", "org_id"),
        Index("ix_employees_org_id_ist_aktiv", "org_id", "ist_aktiv"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False)
    vorname: Mapped[str] = mapped_column(String, nullable=False)
    nachname: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eintrittsdatum: Mapped[date] = mapped_column(Date, nullable=False)
    austrittsdatum: Mapped[date | None] = mapped_column(Date, nullable=True)
    ist_aktiv: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    # ── Module PCM ──────────────────────────────────────────────────
    employee_type: Mapped[EmployeeType] = mapped_column(
        pg_enum(EmployeeType),
        default=EmployeeType.REGULAR,
        server_default="REGULAR",
        nullable=False,
    )
    # External-system identifier (Personalnummer / Personio ID / DATEV Konto)
    # used to map rows on payroll import. Nullable, no uniqueness yet.
    employee_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="employees")
    contracts: Mapped[list[EmployeeContract]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )
    payrolls: Mapped[list[MonthlyPayroll]] = relationship(back_populates="employee")


class EmployeeContract(Base):
    __tablename__ = "employee_contracts"
    __table_args__ = (
        Index("ix_employee_contracts_org_id", "org_id"),
        Index("ix_employee_contracts_employee_id", "employee_id"),
        Index("ix_employee_contracts_employee_id_gueltig_ab", "employee_id", "gueltig_ab"),
        Index("ix_employee_contracts_salary_tariff_id", "salary_tariff_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    vertragsart: Mapped[Vertragsart] = mapped_column(pg_enum(Vertragsart), nullable=False)
    assigned_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tarifwerk: Mapped[Tarifwerk | None] = mapped_column(pg_enum(Tarifwerk), nullable=True)
    entgeltgruppe: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stufe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gueltig_ab: Mapped[date] = mapped_column(Date, nullable=False)
    gueltig_bis: Mapped[date | None] = mapped_column(Date, nullable=True)
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ── Module PCM ──────────────────────────────────────────────────
    # A contract *is* the spec's "salary assignment" (Gehaltsvereinbarung).
    allocation_method: Mapped[AllocationMethod] = mapped_column(
        pg_enum(AllocationMethod),
        default=AllocationMethod.ACTUAL_HOURS,
        server_default="ACTUAL_HOURS",
        nullable=False,
    )
    # Manual promotion-date override. The Promotion Job reads but never writes it.
    next_level_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Optional link to the PCM tariff table (validity-window aware).
    salary_tariff_id: Mapped[str | None] = mapped_column(
        ForeignKey("salary_tariffs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    employee: Mapped[Employee] = relationship(back_populates="contracts")
    components: Mapped[list[SalaryComponent]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    salary_tariff: Mapped[SalaryTariff | None] = relationship(
        "SalaryTariff", foreign_keys=[salary_tariff_id]
    )


class SalaryComponent(Base):
    __tablename__ = "salary_components"
    __table_args__ = (
        Index("ix_salary_components_org_id", "org_id"),
        Index("ix_salary_components_contract_id", "contract_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("employee_contracts.id", ondelete="CASCADE"), nullable=False
    )
    typ: Mapped[SalaryComponentTyp] = mapped_column(
        pg_enum(SalaryComponentTyp), nullable=False
    )
    bezeichnung: Mapped[str] = mapped_column(String(100), nullable=False)
    betrag: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    nach_multiplikator: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    einmalig: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    gilt_fuer_monat: Mapped[date | None] = mapped_column(Date, nullable=True)
    ist_aktiv: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    contract: Mapped[EmployeeContract] = relationship(back_populates="components")


class EmployerGrossFactor(Base):
    __tablename__ = "employer_gross_factors"
    __table_args__ = (
        Index("ix_employer_gross_factors_org_id", "org_id"),
        Index(
            "ix_employer_gross_factors_org_id_vertragsart_gueltig_ab",
            "org_id",
            "vertragsart",
            "gueltig_ab",
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    vertragsart: Mapped[Vertragsart] = mapped_column(pg_enum(Vertragsart), nullable=False)
    faktor: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    gueltig_ab: Mapped[date] = mapped_column(Date, nullable=False)
    gueltig_bis: Mapped[date | None] = mapped_column(Date, nullable=True)
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()

    organization: Mapped[Organization] = relationship(
        back_populates="employer_gross_factors"
    )


class TarifTabelle(Base):
    __tablename__ = "tarif_tabelle"
    __table_args__ = (
        UniqueConstraint("tarifwerk", "entgeltgruppe", "stufe", "jahr"),
        Index("ix_tarif_tabelle_tarifwerk_jahr", "tarifwerk", "jahr"),
    )

    id: Mapped[str] = cuid_pk()
    tarifwerk: Mapped[Tarifwerk] = mapped_column(pg_enum(Tarifwerk), nullable=False)
    entgeltgruppe: Mapped[str] = mapped_column(String(20), nullable=False)
    stufe: Mapped[int] = mapped_column(Integer, nullable=False)
    jahr: Mapped[int] = mapped_column(Integer, nullable=False)
    betrag: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = created_at()


class MonthlyPayroll(Base):
    __tablename__ = "monthly_payrolls"
    __table_args__ = (
        UniqueConstraint("org_id", "employee_id", "monat"),
        Index("ix_monthly_payrolls_org_id", "org_id"),
        Index("ix_monthly_payrolls_org_id_fiscal_year_id", "org_id", "fiscal_year_id"),
        Index("ix_monthly_payrolls_employee_id_monat", "employee_id", "monat"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False
    )
    monat: Mapped[date] = mapped_column(Date, nullable=False)

    assigned_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    standard_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    ag_faktor: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)

    actual_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    betrag_an_brutto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    betrag_ag_brutto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # ── Module PCM ──────────────────────────────────────────────────
    # AN/AG-Brutto are already covered by betrag_an_brutto / betrag_ag_brutto.
    # BAV (employer pension) and fringe benefits (Jobticket etc.) are tracked
    # separately for the VWN itemized breakdown.
    bav_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal(0), server_default="0", nullable=False
    )
    fringe_benefits_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal(0), server_default="0", nullable=False
    )
    status: Mapped[PayrollStatus] = mapped_column(
        pg_enum(PayrollStatus),
        default=PayrollStatus.CALCULATED,
        server_default="CALCULATED",
        nullable=False,
    )

    quelle: Mapped[str] = mapped_column(
        String, default="MANUELL", server_default="MANUELL", nullable=False
    )
    import_batch_id: Mapped[str | None] = mapped_column(String, nullable=True)  # no FK
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="monthly_payrolls")
    employee: Mapped[Employee] = relationship(back_populates="payrolls")
    fiscal_year: Mapped[FiscalYear] = relationship()
    allocations: Mapped[list[PayrollAllocation]] = relationship(
        back_populates="payroll", cascade="all, delete-orphan"
    )
    components: Mapped[list[PayrollComponent]] = relationship(
        back_populates="payroll", cascade="all, delete-orphan"
    )
    detail_lines: Mapped[list[PayrollDetailLine]] = relationship(
        "PayrollDetailLine", back_populates="payroll", cascade="all, delete-orphan"
    )


class PayrollComponent(Base):
    __tablename__ = "payroll_components"
    __table_args__ = (Index("ix_payroll_components_payroll_id", "payroll_id"),)

    id: Mapped[str] = cuid_pk()
    payroll_id: Mapped[str] = mapped_column(
        ForeignKey("monthly_payrolls.id", ondelete="CASCADE"), nullable=False
    )
    typ: Mapped[SalaryComponentTyp] = mapped_column(
        pg_enum(SalaryComponentTyp), nullable=False
    )
    bezeichnung: Mapped[str] = mapped_column(String(100), nullable=False)
    betrag: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    nach_multiplikator: Mapped[bool] = mapped_column(Boolean, nullable=False)

    payroll: Mapped[MonthlyPayroll] = relationship(back_populates="components")


class PayrollAllocation(Base):
    __tablename__ = "payroll_allocations"
    __table_args__ = (
        Index("ix_payroll_allocations_org_id", "org_id"),
        Index("ix_payroll_allocations_payroll_id", "payroll_id"),
        Index("ix_payroll_allocations_cost_center_id", "cost_center_id"),
        Index("ix_payroll_allocations_funding_measure_id", "funding_measure_id"),
        Index(
            "ix_payroll_allocations_finanzplan_position_id", "finanzplan_position_id"
        ),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    payroll_id: Mapped[str] = mapped_column(
        ForeignKey("monthly_payrolls.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=False
    )
    prozent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    betrag_anteil: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    allocation_key_id: Mapped[str | None] = mapped_column(
        ForeignKey("allocation_keys.id", ondelete="SET NULL"), nullable=True
    )
    # ── Module PCM ──────────────────────────────────────────────────
    # origin scopes the re-run delete/rewrite: only PCM rows are replaced.
    origin: Mapped[AllocationOrigin] = mapped_column(
        pg_enum(AllocationOrigin),
        default=AllocationOrigin.MANUELL,
        server_default="MANUELL",
        nullable=False,
    )
    # PCM attributes each share to a grant project / finanzplan position.
    funding_measure_id: Mapped[str | None] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="SET NULL"), nullable=True
    )
    finanzplan_position_id: Mapped[str | None] = mapped_column(
        ForeignKey("finanzplan_positionen.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    payroll: Mapped[MonthlyPayroll] = relationship(back_populates="allocations")
    cost_center: Mapped[CostCenter] = relationship()
    allocation_key: Mapped[AllocationKey | None] = relationship()
    funding_measure: Mapped[FundingMeasure | None] = relationship(
        "FundingMeasure", foreign_keys=[funding_measure_id]
    )
    finanzplan_position: Mapped[FinanzplanPosition | None] = relationship(
        "FinanzplanPosition", foreign_keys=[finanzplan_position_id]
    )
