"""Unit tests for rule-based chart selection. Fixed result sets, no LLM."""

from __future__ import annotations

import datetime

from app.query.charts import pick_chart


def test_single_numeric_value_is_a_kpi() -> None:
    chart = pick_chart(["total_revenue"], [[125000]])
    assert chart.type == "kpi"
    assert chart.y == ["total_revenue"]


def test_empty_result_falls_back_to_table() -> None:
    chart = pick_chart(["a", "b"], [])
    assert chart.type == "table"


def test_temporal_plus_numeric_is_a_line() -> None:
    rows = [
        [datetime.date(2024, 1, 1), 100],
        [datetime.date(2024, 2, 1), 140],
        [datetime.date(2024, 3, 1), 90],
    ]
    chart = pick_chart(["month", "revenue"], rows)
    assert chart.type == "line"
    assert chart.x == "month"
    assert chart.y == ["revenue"]


def test_category_and_single_measure_with_few_rows_is_a_pie() -> None:
    rows = [["Engineering", 40], ["Sales", 30], ["Marketing", 20]]
    chart = pick_chart(["department", "headcount"], rows)
    assert chart.type == "pie"


def test_category_and_measure_with_many_rows_is_a_bar() -> None:
    rows = [[f"dept_{i}", i * 10] for i in range(15)]
    chart = pick_chart(["department", "headcount"], rows)
    assert chart.type == "bar"


def test_category_with_multiple_measures_is_a_bar_not_pie() -> None:
    rows = [["Engineering", 40, 2800000], ["Sales", 30, 2100000]]
    chart = pick_chart(["department", "headcount", "total_salary"], rows)
    assert chart.type == "bar"
    assert chart.y == ["headcount", "total_salary"]


def test_two_numerics_is_a_scatter() -> None:
    rows = [[i, i * 2.5] for i in range(20)]
    chart = pick_chart(["hours_worked", "output_units"], rows)
    assert chart.type == "scatter"


def test_too_many_categories_falls_back_to_table() -> None:
    rows = [[f"item_{i}", i] for i in range(50)]
    chart = pick_chart(["item", "value"], rows)
    assert chart.type == "table"


def test_wide_text_result_falls_back_to_table() -> None:
    rows = [["Aarav Sharma", "aarav@example.com", "Bangalore"]]
    chart = pick_chart(["name", "email", "city"], rows)
    assert chart.type == "table"


def test_boolean_column_treated_like_a_category() -> None:
    rows = [[True, 105], [False, 15]]
    chart = pick_chart(["is_active", "headcount"], rows)
    assert chart.type == "pie"


def test_year_named_numeric_column_is_treated_as_a_time_axis() -> None:
    """SELECT EXTRACT(YEAR FROM ...) AS hire_year, COUNT(*) is two integer
    columns with no type distinguishing them — without the name heuristic
    this reads as "two numerics" and gets charted as a scatter plot."""
    rows = [[2021, 20], [2022, 24], [2023, 30], [2024, 46]]
    chart = pick_chart(["hire_year", "hires"], rows)
    assert chart.type == "line"
    assert chart.x == "hire_year"
    assert chart.y == ["hires"]


def test_bare_year_value_is_still_a_kpi_not_reclassified() -> None:
    """A single year-named column with no other numeric measure should not
    be promoted away from the KPI rule — there'd be nothing left to chart."""
    chart = pick_chart(["founding_year"], [[1998]])
    assert chart.type == "kpi"
