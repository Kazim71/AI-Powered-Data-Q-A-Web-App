"""Unit tests for identifier normalisation. No DuckDB, no app — pure functions."""

from __future__ import annotations

import pytest

from app.ingestion.naming import (
    deduplicate,
    normalise_columns,
    slugify,
    table_name_for,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Employee ID", "employee_id"),
        ("  Total Revenue (₹) ", "total_revenue"),
        ("Café Sales", "cafe_sales"),
        ("2024 Q1", "c_2024_q1"),        # identifiers can't start with a digit
        ("select", "select_col"),        # reserved word
        ("Base Salary (INR)", "base_salary_inr"),
        ("---", "col"),                  # nothing usable left -> fallback
        ("Unnamed: 3", "unnamed_3"),     # pandas' placeholder for blank headers
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_deduplicate_preserves_order() -> None:
    assert deduplicate(["notes", "id", "notes", "notes"]) == [
        "notes", "id", "notes_2", "notes_3",
    ]


def test_normalise_columns_keeps_original_labels() -> None:
    clean, labels = normalise_columns(["Notes", "notes", "Hire Date"])
    assert clean == ["notes", "notes_2", "hire_date"]
    assert labels == {"notes": "Notes", "notes_2": "notes", "hire_date": "Hire Date"}


@pytest.mark.parametrize(
    ("filename", "sheet", "expected"),
    [
        ("employees.csv", None, "employees"),
        ("Q1 Sales.xlsx", "By Region", "q1_sales_by_region"),
        ("salaries.xlsx", "2023", "salaries_2023"),   # no ugly c_ in a suffix
        ("sales.xlsx", "Sales", "sales"),             # no sales_sales
    ],
)
def test_table_name_for(filename: str, sheet: str | None, expected: str) -> None:
    assert table_name_for(filename, sheet) == expected
