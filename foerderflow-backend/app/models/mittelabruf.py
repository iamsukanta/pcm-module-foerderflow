"""Mittelabruf (mittelabrufe) — a call for committed funds.

INVARIANT: drawn funds must be spent within verwendungsfrist_tage (default 42)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import MittelabrufStatus

if TYPE_CHECKING:
    from app.models.funding import FundingMeasure
    from app.models.master import FiscalYear
    from app.models.organization import Organization


class Mittelabruf(Base):
    __tablename__ = "mittelabrufe"
    __table_args__ = (
        Index("ix_mittelabrufe_org_id", "org_id"),
        Index("ix_mittelabrufe_org_id_funding_measure_id", "org_id", "funding_measure_id"),
        Index("ix_mittelabrufe_org_id_status", "org_id", "status"),
        Index("ix_mittelabrufe_frist_bis", "frist_bis"),
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

    abruf_datum: Mapped[date] = mapped_column(Date, nullable=False)
    betrag: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    verwendungsfrist_tage: Mapped[int] = mapped_column(
        Integer, default=42, server_default="42", nullable=False
    )
    frist_bis: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[MittelabrufStatus] = mapped_column(
        pg_enum(MittelabrufStatus),
        default=MittelabrufStatus.ABGERUFEN,
        server_default="ABGERUFEN",
    )
    betrag_verwendet: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal(0), server_default="0", nullable=False
    )
    betrag_zurueck: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="mittelabrufe")
    funding_measure: Mapped[FundingMeasure] = relationship(back_populates="mittelabrufe")
    fiscal_year: Mapped[FiscalYear] = relationship()
