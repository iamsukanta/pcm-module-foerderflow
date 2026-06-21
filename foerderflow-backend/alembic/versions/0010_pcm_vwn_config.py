"""pcm phase 2 — VWN personnel-cost config (Area M)

Additive: one new table (vwn_personnel_configs). No new enum.

Revision ID: 0010_pcm_vwn_config
Revises: 0009_pcm_forecast_scenarios
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from alembic import op
from app.models.pcm_vwn import VwnPersonnelConfig

revision: str = "0010_pcm_vwn_config"
down_revision: str | None = "0009_pcm_forecast_scenarios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    VwnPersonnelConfig.__table__.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    VwnPersonnelConfig.__table__.drop(op.get_bind(), checkfirst=False)
