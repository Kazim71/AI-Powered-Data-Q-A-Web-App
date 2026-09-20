"""Picks a chart type from an executed result set. No LLM involved.

See docs/decisions/0003-rule-based-chart-selection.md: the model writes SQL
without knowing what the result will look like, so letting it also choose the
chart means it's guessing blind — a bar chart with 400 bars, a line chart for
a single number. This module inspects the *actual* result shape after
execution and picks deterministically, which means it can never reference a
column the result doesn't have, and it's trivially unit-testable with fixed
rows — no network, no model, no flakiness.

Column "kind" here is inferred from the Python types DuckDB returns (int/
float -> numeric, date/datetime -> temporal, bool -> boolean, else text/
categorical). This is coarser than the ingestion profiler's semantic typing
(ingestion/profiler.py), because a query result is arbitrary — a GROUP BY
key might be a source `identifier` column, and there's no schema metadata
left to consult post-aggregation. Accepted limitation; see the module's ADR.

One case from that limitation is worth naming specifically because it's
common: `SELECT EXTRACT(YEAR FROM ...) AS hire_year, COUNT(*) FROM ...` comes
back as two plain integer columns, with nothing marking `hire_year` as a time
axis rather than a second measure — so without help it reads as "two numeric
columns" and gets charted as a scatter plot instead of the trend line it
obviously is. `_looks_temporal_by_name` catches this one specific, very
common shape (a column literally called `year`/`month`/`quarter`/...) by
name, without trying to solve column semantics in general.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Literal

from app.models import ChartSpec

ColumnKind = Literal["numeric", "temporal", "boolean", "other"]

_PIE_MAX_ROWS = 8
_CATEGORY_MAX_ROWS = 30

_TEMPORAL_NAME_HINTS = ("year", "month", "quarter", "week", "period")


def _looks_temporal_by_name(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _TEMPORAL_NAME_HINTS)


def _infer_column_kind(values: list[object]) -> ColumnKind:
    sample = next((v for v in values if v is not None), None)
    if sample is None:
        return "other"
    if isinstance(sample, bool):
        return "boolean"
    if isinstance(sample, (int, float, Decimal)):
        return "numeric"
    if isinstance(sample, (datetime.date, datetime.datetime, datetime.time)):
        return "temporal"
    return "other"


def pick_chart(columns: list[str], rows: list[list[object]]) -> ChartSpec:
    if not rows or not columns:
        return ChartSpec(type="table", reason="No rows to visualise.")

    kinds = [_infer_column_kind([row[i] for row in rows]) for i in range(len(columns))]
    numeric_idx = [i for i, k in enumerate(kinds) if k == "numeric"]
    temporal_idx = [i for i, k in enumerate(kinds) if k == "temporal"]
    other_idx = [i for i, k in enumerate(kinds) if k in ("other", "boolean")]
    row_count = len(rows)

    # A numeric column literally named "year"/"month"/... is a time axis, not
    # a second measure — reclassify it, but only when another numeric column
    # remains as the actual measure. Otherwise leave a bare "SELECT year..."
    # alone, so a single value still renders as a KPI rather than a line with
    # no y-axis.
    if len(numeric_idx) >= 2:
        promoted = [i for i in numeric_idx if _looks_temporal_by_name(columns[i])]
        if promoted and len(promoted) < len(numeric_idx):
            temporal_idx = temporal_idx + promoted
            numeric_idx = [i for i in numeric_idx if i not in promoted]

    numeric_cols = [columns[i] for i in numeric_idx]
    temporal_cols = [columns[i] for i in temporal_idx]
    other_cols = [columns[i] for i in other_idx]

    # A single row of nothing but numbers -> one or more headline figures, not
    # a chart at all. This also covers "compare metric A vs metric B" results
    # (e.g. avg_bonus_2023, avg_bonus_2024 in one row): with only the old
    # single-column check, a 1-row/2-numeric-column result fell all the way
    # through to the "two numerics -> scatter" rule below and rendered as a
    # scatter plot of exactly one point — a real bug, not just an edge case;
    # any two named quantities side by side is a comparison, not a
    # relationship between two variables across observations.
    if row_count == 1 and numeric_cols and not other_cols and not temporal_cols:
        noun = "value" if len(numeric_cols) == 1 else "values"
        return ChartSpec(
            type="kpi", y=numeric_cols, reason=f"A single row of headline {noun}."
        )

    # A time axis plus at least one measure -> trend over time.
    if len(temporal_cols) == 1 and numeric_cols:
        return ChartSpec(
            type="line",
            x=temporal_cols[0],
            y=numeric_cols,
            reason="One time column with numeric measure(s): shown as a trend.",
        )

    # One label column plus measure(s): parts-of-a-whole vs. comparison.
    if len(other_cols) == 1 and numeric_cols and row_count <= _CATEGORY_MAX_ROWS:
        if len(numeric_cols) == 1 and row_count <= _PIE_MAX_ROWS:
            return ChartSpec(
                type="pie",
                x=other_cols[0],
                y=numeric_cols,
                reason=f"One category, one measure, {row_count} slices: a share-of-total view.",
            )
        return ChartSpec(
            type="bar",
            x=other_cols[0],
            y=numeric_cols,
            reason=f"One category column with {row_count} rows: a direct comparison.",
        )

    # Two measures, nothing categorical: relationship between them.
    if len(numeric_cols) == 2 and not other_cols and not temporal_cols:
        return ChartSpec(
            type="scatter",
            x=numeric_cols[0],
            y=[numeric_cols[1]],
            reason="Two numeric columns: shown as a relationship.",
        )

    return ChartSpec(
        type="table",
        reason="The result doesn't fit a single clear chart shape; showing the table.",
    )
