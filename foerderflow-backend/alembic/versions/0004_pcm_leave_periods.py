"""pcm phase 2 — leave & absence (employee_leave_periods)

Module PCM, Area F (Leave & Absence). Purely additive: one new table plus its
``leave_type`` enum. The table's enum type is created/dropped together with the
table by SQLAlchemy metadata; the explicit ENUM drop in downgrade guards cleanup.

Revision ID: 0004_pcm_leave_periods
Revises: 0003_pcm_tariff_softdelete
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.pcm_leave import EmployeeLeavePeriod

revision: str = "0004_pcm_leave_periods"
down_revision: str | None = "0003_pcm_tariff_softdelete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_leave_type = postgresql.ENUM(
    "ELTERNZEIT",
    "MUTTERSCHUTZ",
    "LANGZEITERKRANKUNG",
    "OTHER",
    name="leave_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    # The table's leave_type enum is created together with the table by metadata
    # (native_enum, create_type=True) — do not pre-create it.
    EmployeeLeavePeriod.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    EmployeeLeavePeriod.__table__.drop(bind, checkfirst=False)
    _leave_type.drop(bind, checkfirst=True)
