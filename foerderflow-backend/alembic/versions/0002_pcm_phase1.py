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

# New PCM tables as PINNED DDL, captured once from the metadata at the 0002 point
# in time. Built explicitly rather than from ``Model.__table__.create()`` because
# the live models drift: e.g. ``salary_tariffs.deleted_at`` was added later by
# 0003, so creating from the live model here would create that column early and
# collide with 0003 (DuplicateColumn). Statements are in dependency order; the two
# enum types exclusive to these tables (brutto_type, payroll_detail_component) are
# created/dropped here too.
_NEW_TABLE_CREATE_DDL: tuple[str, ...] = (
    "CREATE TYPE brutto_type AS ENUM ('EMPLOYER', 'EMPLOYEE', 'NEITHER')",
    "CREATE TYPE payroll_detail_component AS ENUM ('BASE', 'ZULAGE', 'BONUS', 'JSZ', 'WEIHNACHTSGELD', 'BAV', 'ADJUST_ADD', 'ADJUST_DED', 'FRINGE')",
    "CREATE TABLE salary_tariffs (\n\tid VARCHAR NOT NULL, \n\torg_id VARCHAR NOT NULL, \n\ttariff_code VARCHAR(50) NOT NULL, \n\tsalary_group VARCHAR(20) NOT NULL, \n\tlevel INTEGER NOT NULL, \n\tmonthly_amount NUMERIC(14, 2) NOT NULL, \n\tstandard_hours NUMERIC(5, 2) NOT NULL, \n\tis_proposed BOOLEAN DEFAULT 'false' NOT NULL, \n\tvalid_from DATE NOT NULL, \n\tvalid_to DATE, \n\tbav_rate_pct NUMERIC(5, 2), \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_salary_tariffs PRIMARY KEY (id), \n\tCONSTRAINT fk_salary_tariffs_org_id_organizations FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT\n)",
    "CREATE INDEX ix_salary_tariffs_lookup ON salary_tariffs (org_id, tariff_code, salary_group, level, is_proposed)",
    "CREATE INDEX ix_salary_tariffs_org_id ON salary_tariffs (org_id)",
    "CREATE TABLE wochenstunden_zuweisungen (\n\tid VARCHAR NOT NULL, \n\torg_id VARCHAR NOT NULL, \n\temployee_id VARCHAR NOT NULL, \n\tsalary_assignment_id VARCHAR NOT NULL, \n\tcost_center_id VARCHAR NOT NULL, \n\tfunding_measure_id VARCHAR, \n\tfinanzplan_position_id VARCHAR, \n\tweekly_hours NUMERIC(5, 2) NOT NULL, \n\teffective_date DATE NOT NULL, \n\tend_date DATE, \n\tnote TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_wochenstunden_zuweisungen PRIMARY KEY (id), \n\tCONSTRAINT fk_wochenstunden_zuweisungen_org_id_organizations FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_wochenstunden_zuweisungen_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_wochenstunden_zuweisungen_salary_assignment_id_emplo_dd23 FOREIGN KEY(salary_assignment_id) REFERENCES employee_contracts (id) ON DELETE CASCADE, \n\tCONSTRAINT fk_wochenstunden_zuweisungen_cost_center_id_cost_centers FOREIGN KEY(cost_center_id) REFERENCES cost_centers (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_wochenstunden_zuweisungen_funding_measure_id_funding_b825 FOREIGN KEY(funding_measure_id) REFERENCES funding_measures (id) ON DELETE SET NULL, \n\tCONSTRAINT fk_wochenstunden_zuweisungen_finanzplan_position_id_fin_b3ab FOREIGN KEY(finanzplan_position_id) REFERENCES finanzplan_positionen (id) ON DELETE SET NULL\n)",
    "CREATE INDEX ix_wochenstunden_zuweisungen_salary_assignment_id ON wochenstunden_zuweisungen (salary_assignment_id)",
    "CREATE INDEX ix_wochenstunden_zuweisungen_org_id ON wochenstunden_zuweisungen (org_id)",
    "CREATE INDEX ix_wochenstunden_zuweisungen_cost_center_id ON wochenstunden_zuweisungen (cost_center_id)",
    "CREATE INDEX ix_wochenstunden_zuweisungen_employee_id ON wochenstunden_zuweisungen (employee_id)",
    "CREATE INDEX ix_wochenstunden_zuweisungen_funding_measure_id ON wochenstunden_zuweisungen (funding_measure_id)",
    "CREATE INDEX ix_wochenstunden_zuweisungen_employee_id_effective_date ON wochenstunden_zuweisungen (employee_id, effective_date)",
    "CREATE TABLE payroll_detail_lines (\n\tid VARCHAR NOT NULL, \n\torg_id VARCHAR NOT NULL, \n\tmonthly_payroll_id VARCHAR NOT NULL, \n\tcomponent payroll_detail_component NOT NULL, \n\tdescription VARCHAR(200) NOT NULL, \n\tamount NUMERIC(14, 2) NOT NULL, \n\tbrutto_type brutto_type NOT NULL, \n\tsource_record_id VARCHAR, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_payroll_detail_lines PRIMARY KEY (id), \n\tCONSTRAINT fk_payroll_detail_lines_monthly_payroll_id_monthly_payrolls FOREIGN KEY(monthly_payroll_id) REFERENCES monthly_payrolls (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_payroll_detail_lines_monthly_payroll_id ON payroll_detail_lines (monthly_payroll_id)",
    "CREATE INDEX ix_payroll_detail_lines_org_id ON payroll_detail_lines (org_id)",
    "CREATE TABLE salary_levels (\n\tid VARCHAR NOT NULL, \n\torg_id VARCHAR NOT NULL, \n\ttariff_id VARCHAR NOT NULL, \n\tsalary_group VARCHAR(20) NOT NULL, \n\tlevel_no INTEGER NOT NULL, \n\tmonthly_amount NUMERIC(14, 2) NOT NULL, \n\tmonths_to_next_level INTEGER, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_salary_levels PRIMARY KEY (id), \n\tCONSTRAINT uq_salary_levels_tariff_id UNIQUE (tariff_id, salary_group, level_no), \n\tCONSTRAINT fk_salary_levels_org_id_organizations FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_salary_levels_tariff_id_salary_tariffs FOREIGN KEY(tariff_id) REFERENCES salary_tariffs (id) ON DELETE CASCADE\n)",
    "CREATE INDEX ix_salary_levels_org_id ON salary_levels (org_id)",
    "CREATE INDEX ix_salary_levels_tariff_id ON salary_levels (tariff_id)",
)

_NEW_TABLE_DROP_DDL: tuple[str, ...] = (
    "DROP TABLE salary_levels",
    "DROP TABLE payroll_detail_lines",
    "DROP TABLE wochenstunden_zuweisungen",
    "DROP TABLE salary_tariffs",
    "DROP TYPE brutto_type",
    "DROP TYPE payroll_detail_component",
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Pre-create enum types referenced by ADD COLUMN on existing tables.
    for enum in _EXISTING_TABLE_ENUMS:
        enum.create(bind, checkfirst=True)

    # 2) Create new PCM tables (pinned DDL; their indexes + own enum types come
    #    along). salary_tariffs must exist before the employee_contracts FK below.
    for statement in _NEW_TABLE_CREATE_DDL:
        op.execute(statement)

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

    # Drop new tables in reverse dependency order (pinned DDL also drops their own
    # enum types, brutto_type & payroll_detail_component).
    for statement in _NEW_TABLE_DROP_DDL:
        op.execute(statement)

    # Drop remaining PCM enum types. checkfirst guards the new-table enums that
    # were already removed with their table above.
    for enum in (
        *_EXISTING_TABLE_ENUMS,
        _brutto_type,
        _payroll_detail_component,
    ):
        enum.drop(bind, checkfirst=True)
