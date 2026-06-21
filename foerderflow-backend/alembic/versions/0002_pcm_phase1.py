"""pcm phase 1 — additive Personal Cost Management schema

Module PCM, Phase 1 (data modeling). Purely additive: new tables plus
nullable / server-defaulted columns on existing tables. No existing column is
altered or dropped, so the change is backward-compatible and needs no data
migration.

New tables:
  salary_tariffs · salary_levels · wochenstunden_zuweisungen · payroll_detail_lines

Additive columns:
  employees.employee_type, .employee_external_id
  employee_contracts.allocation_method, .next_level_date, .salary_tariff_id
  monthly_payrolls.bav_amount, .fringe_benefits_amount, .status
  payroll_allocations.origin, .funding_measure_id, .finanzplan_position_id
  funding_measures.allows_plan_based_allocation

Enum gotcha: enum types added as columns on *existing* tables are not emitted by
autogenerate, so they are created/dropped explicitly here (create_type=False on
the column refs; CREATE/DROP TYPE managed manually). Enum types used only by new
tables are created/dropped together with their table by SQLAlchemy metadata.

Revision ID: 0002_pcm_phase1
Revises: 0001_initial
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.pcm_payroll import PayrollDetailLine
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryLevel, SalaryTariff

revision: str = "0002_pcm_phase1"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Enum types added as columns on EXISTING tables — managed explicitly.
_employee_type = postgresql.ENUM(
    "REGULAR", "PLACEHOLDER", name="employee_type", create_type=False
)
_allocation_method = postgresql.ENUM(
    "ACTUAL_HOURS", "PLAN_PERCENTAGE", name="allocation_method", create_type=False
)
_payroll_status = postgresql.ENUM(
    "CALCULATED", "ERROR", "ON_LEAVE", name="payroll_status", create_type=False
)
_allocation_origin = postgresql.ENUM(
    "MANUELL", "PCM", name="allocation_origin", create_type=False
)
_EXISTING_TABLE_ENUMS = (
    _employee_type,
    _allocation_method,
    _payroll_status,
    _allocation_origin,
)

# Enum types used only by the new payroll_detail_lines table — created/dropped
# with the table by metadata; listed only so downgrade can guarantee cleanup.
_brutto_type = postgresql.ENUM(
    "EMPLOYER", "EMPLOYEE", "NEITHER", name="brutto_type", create_type=False
)
_payroll_detail_component = postgresql.ENUM(
    "BASE",
    "ZULAGE",
    "BONUS",
    "JSZ",
    "WEIHNACHTSGELD",
    "BAV",
    "ADJUST_ADD",
    "ADJUST_DED",
    "FRINGE",
    name="payroll_detail_component",
    create_type=False,
)

# Reverse dependency order is handled by reversed() in downgrade.
_NEW_TABLES = (
    SalaryTariff.__table__,
    SalaryLevel.__table__,
    WochenstundenZuweisung.__table__,
    PayrollDetailLine.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Pre-create enum types referenced by ADD COLUMN on existing tables.
    for enum in _EXISTING_TABLE_ENUMS:
        enum.create(bind, checkfirst=True)

    # 2) Create new PCM tables (their indexes + own enum types come along).
    #    salary_tariffs must exist before the employee_contracts FK below.
    for table in _NEW_TABLES:
        table.create(bind, checkfirst=False)

    # 3) Additive columns on existing tables.
    op.add_column(
        "employees",
        sa.Column(
            "employee_type", _employee_type, nullable=False, server_default="REGULAR"
        ),
    )
    op.add_column(
        "employees",
        sa.Column("employee_external_id", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "employee_contracts",
        sa.Column(
            "allocation_method",
            _allocation_method,
            nullable=False,
            server_default="ACTUAL_HOURS",
        ),
    )
    op.add_column(
        "employee_contracts", sa.Column("next_level_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "employee_contracts", sa.Column("salary_tariff_id", sa.String(), nullable=True)
    )
    op.create_index(
        "ix_employee_contracts_salary_tariff_id",
        "employee_contracts",
        ["salary_tariff_id"],
    )
    op.create_foreign_key(
        "fk_employee_contracts_salary_tariff",
        "employee_contracts",
        "salary_tariffs",
        ["salary_tariff_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "monthly_payrolls",
        sa.Column(
            "bav_amount", sa.Numeric(14, 2), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "monthly_payrolls",
        sa.Column(
            "fringe_benefits_amount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "monthly_payrolls",
        sa.Column(
            "status", _payroll_status, nullable=False, server_default="CALCULATED"
        ),
    )

    op.add_column(
        "payroll_allocations",
        sa.Column(
            "origin", _allocation_origin, nullable=False, server_default="MANUELL"
        ),
    )
    op.add_column(
        "payroll_allocations",
        sa.Column("funding_measure_id", sa.String(), nullable=True),
    )
    op.add_column(
        "payroll_allocations",
        sa.Column("finanzplan_position_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_payroll_allocations_funding_measure_id",
        "payroll_allocations",
        ["funding_measure_id"],
    )
    op.create_index(
        "ix_payroll_allocations_finanzplan_position_id",
        "payroll_allocations",
        ["finanzplan_position_id"],
    )
    op.create_foreign_key(
        "fk_payroll_alloc_funding_measure",
        "payroll_allocations",
        "funding_measures",
        ["funding_measure_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_payroll_alloc_finanzplan_position",
        "payroll_allocations",
        "finanzplan_positionen",
        ["finanzplan_position_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "funding_measures",
        sa.Column(
            "allows_plan_based_allocation",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_column("funding_measures", "allows_plan_based_allocation")

    op.drop_constraint(
        "fk_payroll_alloc_finanzplan_position",
        "payroll_allocations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_payroll_alloc_funding_measure",
        "payroll_allocations",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_payroll_allocations_finanzplan_position_id",
        table_name="payroll_allocations",
    )
    op.drop_index(
        "ix_payroll_allocations_funding_measure_id", table_name="payroll_allocations"
    )
    op.drop_column("payroll_allocations", "finanzplan_position_id")
    op.drop_column("payroll_allocations", "funding_measure_id")
    op.drop_column("payroll_allocations", "origin")

    op.drop_column("monthly_payrolls", "status")
    op.drop_column("monthly_payrolls", "fringe_benefits_amount")
    op.drop_column("monthly_payrolls", "bav_amount")

    op.drop_constraint(
        "fk_employee_contracts_salary_tariff",
        "employee_contracts",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_employee_contracts_salary_tariff_id", table_name="employee_contracts"
    )
    op.drop_column("employee_contracts", "salary_tariff_id")
    op.drop_column("employee_contracts", "next_level_date")
    op.drop_column("employee_contracts", "allocation_method")

    op.drop_column("employees", "employee_external_id")
    op.drop_column("employees", "employee_type")

    # Drop new tables in reverse dependency order (also drops their own enum
    # types, brutto_type & payroll_detail_component).
    for table in reversed(_NEW_TABLES):
        table.drop(bind, checkfirst=False)

    # Drop remaining PCM enum types. checkfirst guards the new-table enums that
    # were already removed with their table above.
    for enum in (
        *_EXISTING_TABLE_ENUMS,
        _brutto_type,
        _payroll_detail_component,
    ):
        enum.drop(bind, checkfirst=True)
