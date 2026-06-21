"""pcm phase 2 — payroll period lock (Area I)

Additive: one new table (payroll_periods) plus its ``payroll_period_status`` enum,
created together with the table by metadata.

Revision ID: 0007_pcm_payroll_periods
Revises: 0006_pcm_audit_log
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.pcm_period import PayrollPeriod

revision: str = "0007_pcm_payroll_periods"
down_revision: str | None = "0006_pcm_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_status = postgresql.ENUM(
    "OPEN", "LOCKED", name="payroll_period_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    PayrollPeriod.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    PayrollPeriod.__table__.drop(bind, checkfirst=False)
    _status.drop(bind, checkfirst=True)
