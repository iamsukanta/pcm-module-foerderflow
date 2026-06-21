"""pcm phase 2 — tariff registry soft-delete

Module PCM, Phase 2 (Tariff Registry). Additive: a single nullable
``deleted_at`` timestamp on ``salary_tariffs`` so that tariff rows referenced by
historical payroll/forecast data can be retired (soft-deleted) without losing the
audit trail, per the Tariff Registry DevGuide (§4.5 "soft-delete preferred").

All Tariff Registry reads filter ``deleted_at IS NULL``; the overlap guard and the
per-month resolver ignore soft-deleted rows.

Revision ID: 0003_pcm_tariff_softdelete
Revises: 0002_pcm_phase1
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_pcm_tariff_softdelete"
down_revision: str | None = "0002_pcm_phase1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "salary_tariffs",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_salary_tariffs_deleted_at", "salary_tariffs", ["deleted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_salary_tariffs_deleted_at", table_name="salary_tariffs")
    op.drop_column("salary_tariffs", "deleted_at")
