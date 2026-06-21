"""pcm phase 2 — personnel cost forecast (Area K)

Additive: one new table (personal_cost_forecasts). No new enum (the data-quality
``warning`` is a plain string column).

Revision ID: 0008_pcm_cost_forecast
Revises: 0007_pcm_payroll_periods
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from alembic import op
from app.models.pcm_forecast import PersonalCostForecast

revision: str = "0008_pcm_cost_forecast"
down_revision: str | None = "0007_pcm_payroll_periods"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    PersonalCostForecast.__table__.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    PersonalCostForecast.__table__.drop(op.get_bind(), checkfirst=False)
