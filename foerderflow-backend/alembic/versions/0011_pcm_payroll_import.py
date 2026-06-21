"""pcm phase 2 — external payroll import batches (Area J)

Additive: one new table (payroll_import_batches) plus its two enums
(import_source_type, payroll_import_status), created with the table by metadata.

Revision ID: 0011_pcm_payroll_import
Revises: 0010_pcm_vwn_config
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.pcm_import import PayrollImportBatch

revision: str = "0011_pcm_payroll_import"
down_revision: str | None = "0010_pcm_vwn_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_source = postgresql.ENUM(
    "CSV_QUARTERLY", "DATEV_EXTF", "PERSONIO", "DIAMANT_BAB",
    name="import_source_type", create_type=False,
)
_status = postgresql.ENUM(
    "PENDING", "MAPPED", "CONFIRMED", "PROCESSED", "ERROR",
    name="payroll_import_status", create_type=False,
)


def upgrade() -> None:
    PayrollImportBatch.__table__.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    PayrollImportBatch.__table__.drop(bind, checkfirst=False)
    _status.drop(bind, checkfirst=True)
    _source.drop(bind, checkfirst=True)
