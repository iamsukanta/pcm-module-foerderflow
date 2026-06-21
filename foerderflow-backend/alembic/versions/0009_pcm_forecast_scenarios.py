"""pcm phase 2 — forecast scenarios (Area L)

Additive: two new tables (forecast_scenarios, forecast_scenario_rows) plus the
``scenario_status`` enum (created with forecast_scenarios by metadata).

Revision ID: 0009_pcm_forecast_scenarios
Revises: 0008_pcm_cost_forecast
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.pcm_scenario import ForecastScenario, ForecastScenarioRow

revision: str = "0009_pcm_forecast_scenarios"
down_revision: str | None = "0008_pcm_cost_forecast"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_status = postgresql.ENUM(
    "DRAFT", "COMPUTED", "PROMOTED", name="scenario_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    ForecastScenario.__table__.create(bind, checkfirst=False)
    ForecastScenarioRow.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    ForecastScenarioRow.__table__.drop(bind, checkfirst=False)
    ForecastScenario.__table__.drop(bind, checkfirst=False)
    _status.drop(bind, checkfirst=True)
