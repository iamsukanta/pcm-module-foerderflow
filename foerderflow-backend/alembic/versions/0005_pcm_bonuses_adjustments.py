"""pcm phase 2 — bonuses & salary adjustments (Areas G & H)

Additive: three new tables (bonus_templates, bonus_payments, salary_adjustments)
plus four new enum types (bonus_type, proration_rule, bonus_applicable_to,
adjustment_type). The brutto_type enum already exists (created in 0002); it is
referenced here with create_type=False.

Enums are pre-created explicitly (the tables share them, so the per-table
auto-CREATE TYPE that SQLAlchemy metadata would emit is suppressed via
create_type=False on every enum reference).

Revision ID: 0005_pcm_bonuses_adjustments
Revises: 0004_pcm_leave_periods
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_pcm_bonuses_adjustments"
down_revision: str | None = "0004_pcm_leave_periods"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_bonus_type = postgresql.ENUM(
    "FIXED", "PERCENT", "REFERENCE_MONTH", name="bonus_type", create_type=False
)
_proration_rule = postgresql.ENUM(
    "FULL", "HOURS_PRORATED", name="proration_rule", create_type=False
)
_applicable_to = postgresql.ENUM(
    "ALL", "PROJECT_ONLY", "OVERHEAD_ONLY",
    name="bonus_applicable_to", create_type=False,
)
_adjustment_type = postgresql.ENUM(
    "ADDITION", "DEDUCTION", name="adjustment_type", create_type=False
)
_brutto_type = postgresql.ENUM(
    "EMPLOYER", "EMPLOYEE", "NEITHER", name="brutto_type", create_type=False
)

_NEW_ENUMS = (_bonus_type, _proration_rule, _applicable_to, _adjustment_type)


def _ts(col: str) -> sa.Column:
    return sa.Column(col, sa.DateTime(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    bind = op.get_bind()
    for enum in _NEW_ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "bonus_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tariff_code", sa.String(length=50), nullable=True),
        sa.Column("salary_group_min", sa.String(length=20), nullable=True),
        sa.Column("salary_group_max", sa.String(length=20), nullable=True),
        sa.Column("applicable_to", _applicable_to, nullable=False, server_default="ALL"),
        sa.Column("type", _bonus_type, nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("brutto_type", _brutto_type, nullable=False),
        sa.Column("proration_rule", _proration_rule, nullable=False, server_default="FULL"),
        sa.Column("reference_month", sa.Integer(), nullable=True),
        sa.Column("payment_month", sa.Integer(), nullable=True),
        sa.Column(
            "prorate_by_employment_period",
            sa.Boolean(), nullable=False, server_default="false",
        ),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_bonus_templates_org_id", "bonus_templates", ["org_id"])

    op.create_table(
        "bonus_payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column(
            "employee_id",
            sa.String(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", _bonus_type, nullable=False),
        sa.Column("amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("brutto_type", _brutto_type, nullable=False),
        sa.Column("proration_rule", _proration_rule, nullable=False, server_default="FULL"),
        sa.Column("reference_month", sa.Integer(), nullable=True),
        sa.Column("payment_month", sa.Integer(), nullable=True),
        sa.Column(
            "prorate_by_employment_period",
            sa.Boolean(), nullable=False, server_default="false",
        ),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column(
            "source_template_id",
            sa.String(),
            sa.ForeignKey("bonus_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_bonus_payments_org_id", "bonus_payments", ["org_id"])
    op.create_index("ix_bonus_payments_employee_id", "bonus_payments", ["employee_id"])

    op.create_table(
        "salary_adjustments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column(
            "employee_id",
            sa.String(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", _adjustment_type, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("brutto_type", _brutto_type, nullable=False),
        sa.Column("proration_rule", _proration_rule, nullable=False, server_default="FULL"),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_salary_adjustments_org_id", "salary_adjustments", ["org_id"])
    op.create_index(
        "ix_salary_adjustments_employee_id", "salary_adjustments", ["employee_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("salary_adjustments")
    op.drop_table("bonus_payments")
    op.drop_table("bonus_templates")
    for enum in _NEW_ENUMS:
        enum.drop(bind, checkfirst=True)
