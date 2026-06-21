"""Module PCM — Forecast scenarios (Area L).

A ``forecast_scenarios`` row holds non-committed what-if parameter overrides
(hour/level overrides, a global tariff growth rate, hypothetical hires). Computing
a scenario produces ``forecast_scenario_rows`` (employee × month baseline vs.
scenario) and stores the totals. Promoting re-runs the committed forecast with the
overrides applied.
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
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import ScenarioStatus

if TYPE_CHECKING:
    pass


class ForecastScenario(Base):
    __tablename__ = "forecast_scenarios"
    __table_args__ = (
        Index("ix_forecast_scenarios_org_id_fiscal_year_id", "org_id", "fiscal_year_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    fiscal_year_id: Mapped[str] = mapped_column(
        ForeignKey("fiscal_years.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ScenarioStatus] = mapped_column(
        pg_enum(ScenarioStatus),
        default=ScenarioStatus.DRAFT,
        server_default="DRAFT",
        nullable=False,
    )
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    baseline_total: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    scenario_total: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    delta_total: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    rows: Mapped[list[ForecastScenarioRow]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class ForecastScenarioRow(Base):
    __tablename__ = "forecast_scenario_rows"
    __table_args__ = (
        Index("ix_forecast_scenario_rows_scenario_id", "scenario_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("forecast_scenarios.id", ondelete="CASCADE"), nullable=False
    )
    # Null for a hypothetical hire (no employee record yet).
    employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    employee_label: Mapped[str] = mapped_column(String(160), nullable=False)
    monat: Mapped[date] = mapped_column(Date, nullable=False)
    baseline_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    scenario_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    delta: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = created_at()

    scenario: Mapped[ForecastScenario] = relationship(back_populates="rows")
