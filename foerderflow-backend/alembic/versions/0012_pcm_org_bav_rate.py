"""pcm phase 2 — org-level BAV rate (Area A.2)

Additive: a single ``bav_rate_pct`` column on ``organizations`` used as the
default BAV rate when a tariff row carries no own override. Defaults to 0 so
existing payroll/forecast behaviour is unchanged until configured.

Revision ID: 0012_pcm_org_bav_rate
Revises: 0011_pcm_payroll_import
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_pcm_org_bav_rate"
down_revision: str | None = "0011_pcm_payroll_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "bav_rate_pct", sa.Numeric(5, 2), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "bav_rate_pct")
