"""Data-layer validation (no DB required): all tables register, mappers
configure cleanly, and PostgreSQL DDL compiles for every table.

Counts: 46 base tables + 14 Module PCM tables (salary_tariffs, salary_levels,
wochenstunden_zuweisungen, payroll_detail_lines, employee_leave_periods,
bonus_templates, bonus_payments, salary_adjustments,
log_employee_salary_assignments, payroll_periods, personal_cost_forecasts,
forecast_scenarios, forecast_scenario_rows, vwn_personnel_configs,
payroll_import_batches) = 61; 24 base enums + 16 PCM
enums (employee_type, allocation_method, payroll_status, brutto_type,
payroll_detail_component, allocation_origin, leave_type, bonus_type,
proration_rule, bonus_applicable_to, adjustment_type, audit_action_type,
payroll_period_status) = 37."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

import app.models  # noqa: F401  (registers tables)
from app.db.base import Base

EXPECTED_TABLE_COUNT = 61
EXPECTED_ENUM_COUNT = 40


def test_all_tables_registered() -> None:
    assert len(Base.metadata.tables) == EXPECTED_TABLE_COUNT


def test_mappers_configure() -> None:
    configure_mappers()  # raises if any relationship is misconfigured


def test_ddl_compiles_for_postgres() -> None:
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        # Raises if a column/constraint can't be rendered for PostgreSQL.
        str(CreateTable(table).compile(dialect=dialect))


def test_enum_count() -> None:
    from enum import Enum

    from app.models import enums

    count = sum(
        1
        for name in dir(enums)
        if isinstance(getattr(enums, name), type)
        and issubclass(getattr(enums, name), Enum)
        and not name.startswith("_")
        and getattr(getattr(enums, name), "__pg_name__", None)
    )
    assert count == EXPECTED_ENUM_COUNT
