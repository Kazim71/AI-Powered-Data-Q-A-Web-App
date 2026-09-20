"""Unit tests for the SQL validation guard. No DuckDB, no LLM — pure parsing."""

from __future__ import annotations

import pytest

from app.core.errors import SQLGenerationError
from app.query.sql_guard import validate_sql

TABLES = {"employees", "departments", "salaries_2023"}


def test_valid_select_passes() -> None:
    result = validate_sql(
        "SELECT department_id, COUNT(*) FROM employees GROUP BY department_id",
        known_tables=TABLES,
        row_cap=100,
    )
    assert result.tables == {"employees"}
    assert "LIMIT" in result.sql.upper()


def test_valid_cte_passes_and_reports_real_tables_only() -> None:
    result = validate_sql(
        """
        WITH active AS (SELECT * FROM employees WHERE is_active = true)
        SELECT department_id, COUNT(*) FROM active GROUP BY department_id
        """,
        known_tables=TABLES,
        row_cap=100,
    )
    # "active" is a CTE alias, not a real table, and must not be reported as one.
    assert result.tables == {"employees"}


def test_join_across_tables_reports_both() -> None:
    result = validate_sql(
        "SELECT d.department_name, AVG(s.base_salary_inr) "
        "FROM employees e "
        "JOIN departments d ON e.department_id = d.id "
        "JOIN salaries_2023 s ON e.employee_id = s.employee_id "
        "GROUP BY d.department_name",
        known_tables=TABLES,
        row_cap=100,
    )
    assert result.tables == {"employees", "departments", "salaries_2023"}


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE employees",
        "DELETE FROM employees",
        "INSERT INTO employees VALUES (1)",
        "UPDATE employees SET is_active = false",
        "CREATE TABLE evil AS SELECT * FROM employees",
        "ALTER TABLE employees ADD COLUMN x INT",
        "ATTACH 'evil.db' AS evil",
        "COPY employees TO 'out.csv'",
        "PRAGMA database_list",
    ],
)
def test_non_select_statements_are_rejected(sql: str) -> None:
    with pytest.raises(SQLGenerationError):
        validate_sql(sql, known_tables=TABLES, row_cap=100)


def test_multiple_statements_are_rejected() -> None:
    with pytest.raises(SQLGenerationError):
        validate_sql(
            "SELECT * FROM employees; DROP TABLE employees;",
            known_tables=TABLES,
            row_cap=100,
        )


def test_unknown_table_is_rejected_with_helpful_detail() -> None:
    with pytest.raises(SQLGenerationError) as exc_info:
        validate_sql("SELECT * FROM secrets", known_tables=TABLES, row_cap=100)
    assert "secrets" in str(exc_info.value.message)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM read_csv_auto('C:/Windows/System32/config')",
        "SELECT current_setting('data_directory')",
        "SELECT getenv('HOME')",
    ],
)
def test_filesystem_and_system_functions_are_blocked(sql: str) -> None:
    with pytest.raises(SQLGenerationError):
        validate_sql(sql, known_tables=TABLES, row_cap=100)


def test_empty_sql_is_rejected() -> None:
    with pytest.raises(SQLGenerationError):
        validate_sql("   ", known_tables=TABLES, row_cap=100)


def test_unparseable_sql_is_rejected() -> None:
    with pytest.raises(SQLGenerationError):
        validate_sql("SELECT FROM WHERE", known_tables=TABLES, row_cap=100)


def test_row_cap_is_injected_as_cap_plus_one_when_missing() -> None:
    result = validate_sql("SELECT * FROM employees", known_tables=TABLES, row_cap=50)
    assert "LIMIT 51" in result.sql.upper()


def test_existing_small_limit_is_preserved() -> None:
    result = validate_sql(
        "SELECT * FROM employees LIMIT 5", known_tables=TABLES, row_cap=1000
    )
    assert "LIMIT 5" in result.sql.upper()
    assert "LIMIT 1001" not in result.sql.upper()


def test_existing_large_limit_is_tightened() -> None:
    result = validate_sql(
        "SELECT * FROM employees LIMIT 999999", known_tables=TABLES, row_cap=100
    )
    assert "LIMIT 101" in result.sql.upper()
