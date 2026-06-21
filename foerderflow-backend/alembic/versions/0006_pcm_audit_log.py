"""pcm phase 2 — salary-assignment audit log (Area O)

Additive: one new table (log_employee_salary_assignments) plus its
``audit_action_type`` enum, created together with the table by metadata.

Revision ID: 0006_pcm_audit_log
Revises: 0005_pcm_bonuses_adjustments
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.pcm_audit import LogEmployeeSalaryAssignment

revision: str = "0006_pcm_audit_log"
down_revision: str | None = "0005_pcm_bonuses_adjustments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_audit_action_type = postgresql.ENUM(
    "UPDATE", "DELETE", "AUTO_PROMOTION", "LEAVE_START", "LEAVE_END",
    name="audit_action_type", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    LogEmployeeSalaryAssignment.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    LogEmployeeSalaryAssignment.__table__.drop(bind, checkfirst=False)
    _audit_action_type.drop(bind, checkfirst=True)
