"""Banking & transactions: BankAccount (bank_accounts), OpeningBalance
(opening_balances), CsvImportProfile (csv_import_profiles), ImportBatch
(import_batches), Transaction (transactions), TransactionSplit (transaction_splits),
FundAllocation (fund_allocations), TransactionBeleg (transaction_belege)."""

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
    AccountTyp,
    ImportFormat,
    TransactionStatus,
    TransactionTyp,
)

if TYPE_CHECKING:
    from app.models.allocation import AllocationKey
    from app.models.booking_rule import BookingRuleApplication
    from app.models.finanzplan import FinanzplanPosition
    from app.models.funding import FundingMeasure
    from app.models.master import CostCenter, FiscalYear, Kostenbereich
    from app.models.organization import Organization


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        UniqueConstraint("org_id", "code"),
        Index("ix_bank_accounts_org_id", "org_id"),
        Index("ix_bank_accounts_org_id_ist_aktiv", "org_id", "ist_aktiv"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    bezeichnung: Mapped[str] = mapped_column(String(120), nullable=False)
    typ: Mapped[AccountTyp] = mapped_column(pg_enum(AccountTyp), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(34), unique=True, nullable=True)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bankname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ist_aktiv: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="bank_accounts")
    opening_balances: Mapped[list[OpeningBalance]] = relationship(
        back_populates="bank_account", cascade="all, delete-orphan"
    )


class OpeningBalance(Base):
    __tablename__ = "opening_balances"
    __table_args__ = (
        UniqueConstraint("bank_account_id", "fiscal_year_id"),
        Index("ix_opening_balances_fiscal_year_id", "fiscal_year_id"),
    )

    id: Mapped[str] = cuid_pk()
    bank_account_id: Mapped[str] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False
    )
    saldo_eroeffnung: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    datum: Mapped[date] = mapped_column(Date, nullable=False)
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    bank_account: Mapped[BankAccount] = relationship(back_populates="opening_balances")
    fiscal_year: Mapped[FiscalYear] = relationship()


class CsvImportProfile(Base):
    __tablename__ = "csv_import_profiles"
    __table_args__ = (
        UniqueConstraint("org_id", "name"),
        Index("ix_csv_import_profiles_org_id", "org_id"),
        Index("ix_csv_import_profiles_ist_systemweit", "ist_systemweit"),
        Index("ix_csv_import_profiles_auto_detect_pattern", "auto_detect_pattern"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    delimiter: Mapped[str] = mapped_column(String(4), nullable=False)
    encoding: Mapped[str] = mapped_column(String(20), nullable=False)
    quote_char: Mapped[str] = mapped_column(
        String(2), default='"', server_default='"', nullable=False
    )
    decimal_separator: Mapped[str] = mapped_column(String(1), nullable=False)
    thousand_separator: Mapped[str | None] = mapped_column(String(1), nullable=True)
    date_format: Mapped[str] = mapped_column(String(20), nullable=False)
    header_row: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    skip_rows: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    column_mappings: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    auto_detect_pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ist_systemweit: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization | None] = relationship(
        back_populates="csv_import_profiles"
    )
    import_batches: Mapped[list[ImportBatch]] = relationship(
        back_populates="csv_import_profile"
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        Index("ix_import_batches_org_id", "org_id"),
        Index("ix_import_batches_org_id_fiscal_year_id", "org_id", "fiscal_year_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False
    )
    format: Mapped[ImportFormat] = mapped_column(pg_enum(ImportFormat), nullable=False)
    csv_import_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("csv_import_profiles.id", ondelete="SET NULL"), nullable=True
    )
    dateiname: Mapped[str] = mapped_column(String, nullable=False)
    anzahl_importiert: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    anzahl_duplikate: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    anzahl_fehler: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    import_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    importiert_von: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = created_at()

    organization: Mapped[Organization] = relationship(back_populates="import_batches")
    fiscal_year: Mapped[FiscalYear] = relationship()
    csv_import_profile: Mapped[CsvImportProfile | None] = relationship(
        back_populates="import_batches"
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="import_batch"
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_org_id", "org_id"),
        Index("ix_transactions_org_id_fiscal_year_id", "org_id", "fiscal_year_id"),
        Index("ix_transactions_org_id_status", "org_id", "status"),
        Index("ix_transactions_org_id_datum", "org_id", "datum"),
        Index("ix_transactions_duplikat_hash", "duplikat_hash"),
        Index("ix_transactions_org_id_kostenbereich_id", "org_id", "kostenbereich_id"),
        Index("ix_transactions_org_id_bank_account_id", "org_id", "bank_account_id"),
        Index("ix_transactions_org_id_iban_partner", "org_id", "iban_partner"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False
    )
    import_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )
    bank_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    datum: Mapped[date] = mapped_column(Date, nullable=False)
    valuta_datum: Mapped[date | None] = mapped_column(Date, nullable=True)
    betrag: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    saldo_nach_buchung: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    typ: Mapped[TransactionTyp] = mapped_column(pg_enum(TransactionTyp), nullable=False)
    auftraggeber: Mapped[str | None] = mapped_column(String(255), nullable=True)
    iban_partner: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bic_partner: Mapped[str | None] = mapped_column(String(11), nullable=True)
    verwendungszweck: Mapped[str | None] = mapped_column(Text, nullable=True)
    externe_referenz: Mapped[str | None] = mapped_column(String(100), nullable=True)
    glaeubiger_id: Mapped[str | None] = mapped_column(String(35), nullable=True)
    mandatsreferenz: Mapped[str | None] = mapped_column(String(35), nullable=True)
    buchungstext_typ: Mapped[str | None] = mapped_column(String(80), nullable=True)
    kostenbereich_id: Mapped[str | None] = mapped_column(
        ForeignKey("kostenbereiche.id", ondelete="SET NULL"), nullable=True
    )
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        pg_enum(TransactionStatus),
        default=TransactionStatus.IMPORTIERT,
        server_default="IMPORTIERT",
    )
    duplikat_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="transactions")
    fiscal_year: Mapped[FiscalYear] = relationship()
    import_batch: Mapped[ImportBatch | None] = relationship(
        back_populates="transactions"
    )
    bank_account: Mapped[BankAccount | None] = relationship()
    kostenbereich: Mapped[Kostenbereich | None] = relationship()
    splits: Mapped[list[TransactionSplit]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    belege: Mapped[list[TransactionBeleg]] = relationship(back_populates="transaction")
    rule_applications: Mapped[list[BookingRuleApplication]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class TransactionSplit(Base):
    __tablename__ = "transaction_splits"
    __table_args__ = (
        Index("ix_transaction_splits_org_id", "org_id"),
        Index("ix_transaction_splits_transaction_id", "transaction_id"),
        Index("ix_transaction_splits_cost_center_id", "cost_center_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=False
    )
    prozent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    betrag_anteil: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    allocation_key_id: Mapped[str | None] = mapped_column(
        ForeignKey("allocation_keys.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    transaction: Mapped[Transaction] = relationship(back_populates="splits")
    cost_center: Mapped[CostCenter] = relationship()
    allocation_key: Mapped[AllocationKey | None] = relationship()
    fund_allocations: Mapped[list[FundAllocation]] = relationship(
        back_populates="transaction_split", cascade="all, delete-orphan"
    )


class FundAllocation(Base):
    __tablename__ = "fund_allocations"
    __table_args__ = (
        UniqueConstraint("transaction_split_id", "funding_measure_id"),
        Index("ix_fund_allocations_org_id", "org_id"),
        Index("ix_fund_allocations_transaction_split_id", "transaction_split_id"),
        Index("ix_fund_allocations_funding_measure_id", "funding_measure_id"),
        Index("ix_fund_allocations_finanzplan_position_id", "finanzplan_position_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    transaction_split_id: Mapped[str] = mapped_column(
        ForeignKey("transaction_splits.id", ondelete="CASCADE"), nullable=False
    )
    funding_measure_id: Mapped[str] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="RESTRICT"), nullable=False
    )
    prozent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal(100), server_default="100", nullable=False
    )
    finanzplan_position_id: Mapped[str | None] = mapped_column(
        ForeignKey("finanzplan_positionen.id", ondelete="SET NULL"), nullable=True
    )
    betrag_foerderfahig: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    betrag_foerderung: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    betrag_eigenanteil: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String, default="VORLAEUFIG", server_default="VORLAEUFIG", nullable=False
    )
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    transaction_split: Mapped[TransactionSplit] = relationship(
        back_populates="fund_allocations"
    )
    funding_measure: Mapped[FundingMeasure] = relationship(
        back_populates="fund_allocations"
    )
    finanzplan_position: Mapped[FinanzplanPosition | None] = relationship(
        back_populates="fund_allocations"
    )


class TransactionBeleg(Base):
    __tablename__ = "transaction_belege"
    __table_args__ = (
        Index("ix_transaction_belege_org_id", "org_id"),
        Index("ix_transaction_belege_transaction_id", "transaction_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False
    )
    datei_pfad: Mapped[str | None] = mapped_column(String(500), nullable=True)
    datei_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    datei_typ: Mapped[str | None] = mapped_column(String(50), nullable=True)
    externe_referenz: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retention_until: Mapped[date] = mapped_column(Date, nullable=False)
    geloescht_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = created_at()

    transaction: Mapped[Transaction] = relationship(back_populates="belege")
