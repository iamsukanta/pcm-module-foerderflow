"""Booking-rule engine: BookingRule (booking_rules), BookingRuleSplit
(booking_rule_splits), BookingRuleApplication (booking_rule_applications).

Match logic = AND over all set conditions; confidence ORANGE→GELB→GRÜN learned via
match_count. BookingRule has TWO FKs to Kostenbereich (match_/set_), so those
relationships are disambiguated with explicit foreign_keys."""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, updated_at

if TYPE_CHECKING:
    from app.models.allocation import AllocationKey
    from app.models.funding import FundingMeasure
    from app.models.master import CostCenter, Kostenbereich
    from app.models.organization import Organization
    from app.models.transaction import Transaction


class BookingRule(Base):
    __tablename__ = "booking_rules"
    __table_args__ = (
        Index("ix_booking_rules_org_id_aktiv", "org_id", "aktiv"),
        Index("ix_booking_rules_funding_measure_id", "funding_measure_id"),
        Index("ix_booking_rules_match_kostenbereich_id", "match_kostenbereich_id"),
        Index("ix_booking_rules_set_kostenbereich_id", "set_kostenbereich_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aktiv: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    prioritaet: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    match_auftraggeber: Mapped[str | None] = mapped_column(String(200), nullable=True)
    match_auftraggeber_exact: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    match_verwendungszweck: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    match_kostenbereich_id: Mapped[str | None] = mapped_column(
        ForeignKey("kostenbereiche.id", ondelete="SET NULL"), nullable=True
    )
    match_iban_partner: Mapped[str | None] = mapped_column(String(34), nullable=True)
    match_betrag_min: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    match_betrag_max: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    match_datum_von: Mapped[date | None] = mapped_column(Date, nullable=True)
    match_datum_bis: Mapped[date | None] = mapped_column(Date, nullable=True)

    set_kostenbereich_id: Mapped[str | None] = mapped_column(
        ForeignKey("kostenbereiche.id", ondelete="SET NULL"), nullable=True
    )

    match_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    confidence: Mapped[str] = mapped_column(
        String(10), default="ORANGE", server_default="ORANGE", nullable=False
    )

    funding_measure_id: Mapped[str | None] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    org: Mapped[Organization] = relationship(back_populates="booking_rules")
    funding_measure: Mapped[FundingMeasure | None] = relationship(
        back_populates="booking_rules"
    )
    match_kostenbereich: Mapped[Kostenbereich | None] = relationship(
        foreign_keys=[match_kostenbereich_id]
    )
    set_kostenbereich: Mapped[Kostenbereich | None] = relationship(
        foreign_keys=[set_kostenbereich_id]
    )
    splits: Mapped[list[BookingRuleSplit]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )
    applications: Mapped[list[BookingRuleApplication]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class BookingRuleSplit(Base):
    __tablename__ = "booking_rule_splits"
    __table_args__ = (
        Index("ix_booking_rule_splits_rule_id", "rule_id"),
        Index("ix_booking_rule_splits_funding_measure_id", "funding_measure_id"),
    )

    id: Mapped[str] = cuid_pk()
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("booking_rules.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[str] = mapped_column(
        ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=False
    )
    prozent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    allocation_key_id: Mapped[str | None] = mapped_column(
        ForeignKey("allocation_keys.id", ondelete="SET NULL"), nullable=True
    )
    funding_measure_id: Mapped[str | None] = mapped_column(
        ForeignKey("funding_measures.id", ondelete="SET NULL"), nullable=True
    )
    allocation_prozent: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    rule: Mapped[BookingRule] = relationship(back_populates="splits")
    cost_center: Mapped[CostCenter] = relationship()
    allocation_key: Mapped[AllocationKey | None] = relationship()
    funding_measure: Mapped[FundingMeasure | None] = relationship(
        back_populates="booking_rule_splits"
    )


class BookingRuleApplication(Base):
    __tablename__ = "booking_rule_applications"
    __table_args__ = (
        Index("ix_booking_rule_applications_org_id", "org_id"),
        Index("ix_booking_rule_applications_transaction_id", "transaction_id"),
        Index("ix_booking_rule_applications_rule_id", "rule_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("booking_rules.id", ondelete="CASCADE"), nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    applied_by: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)

    org: Mapped[Organization] = relationship(
        back_populates="booking_rule_applications"
    )
    transaction: Mapped[Transaction] = relationship(back_populates="rule_applications")
    rule: Mapped[BookingRule] = relationship(back_populates="applications")
