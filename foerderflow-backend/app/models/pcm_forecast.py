"""Module PCM — Personnel cost forecast (Area K).

One row per employee × month within a fiscal year, produced by the forecast
engine. Forecast rows are fully replaced on each run for a fiscal year. The
``warning`` column carries the data-quality flag surfaced on the K.6 warnings
screen (MISSING / DATA_GAP / PROPOSED_TARIFF / ON_LEAVE).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._types import created_at, cuid_pk

if TYPE_CHECKING:
    pass


class PersonalCostForecast(Base):
    __tablename__ = "personal_cost_forecasts"
    __table_args__ = (
        UniqueConstraint("org_id", "fiscal_year_id", "employee_id", "monat"),
        Index("ix_personal_cost_forecasts_org_id_fiscal_year_id", "org_id", "fiscal_year_id"),
        Index("ix_personal_cost_forecasts_employee_id", "employee_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    monat: Mapped[date] = mapped_column(Date, nullable=False)

    forecast_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forecast_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    standard_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    forecast_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    prorated_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    an_brutto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    ag_brutto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    bav_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fringe_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_forecast: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    warning: Mapped[str | None] = mapped_column(String(40), nullable=True)
    components: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    forecast_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = created_at()
