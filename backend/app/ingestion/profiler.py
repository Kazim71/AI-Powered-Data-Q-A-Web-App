"""Column profiling: what the LLM gets to see instead of the data itself.

This is the layer that makes NL->SQL actually work on real files. A bare column
list ("rgn_cd, amt, dt") tells a model almost nothing. A profile that says
`rgn_cd` is categorical with values {EMEA, APAC, AMER} and `dt` is a DATE
spanning 2023-01-01..2024-12-31 lets it write a correct query first time.

Everything here is computed with SQL aggregates inside DuckDB, so profiling a
large table costs one scan and never materialises rows in Python.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.session import Session
from app.models import ColumnProfile, SemanticType, TableProfile

# DuckDB type name fragments -> broad physical family.
_NUMERIC_TYPES = (
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
    "FLOAT", "DOUBLE", "DECIMAL", "REAL",
)
_TEMPORAL_TYPES = ("DATE", "TIMESTAMP", "TIME", "INTERVAL")
_BOOLEAN_TYPES = ("BOOLEAN",)

# Column names that signal an identifier even when stored as an integer.
_ID_NAME_HINTS = ("_id", "id_", "_code", "_key", "_no", "_number", "uuid", "guid")


def _is_numeric(dtype: str) -> bool:
    return any(t in dtype.upper() for t in _NUMERIC_TYPES)


def _is_temporal(dtype: str) -> bool:
    return any(t in dtype.upper() for t in _TEMPORAL_TYPES)


def _looks_like_identifier(name: str) -> bool:
    lowered = name.lower()
    return lowered in {"id", "key", "code"} or any(
        hint in lowered for hint in _ID_NAME_HINTS
    )


def _classify(
    *, name: str, dtype: str, distinct_count: int, row_count: int
) -> SemanticType:
    """Decide how a column should be *used*, not merely how it is stored.

    The distinction matters: an integer `employee_id` must never be summed or
    averaged, and a 3-value integer `status_code` is really a category.
    """
    upper = dtype.upper()

    if any(t in upper for t in _BOOLEAN_TYPES):
        return "boolean"
    if _is_temporal(dtype):
        return "temporal"

    nearly_unique = row_count > 0 and distinct_count >= row_count * 0.95

    # An id-ish name is an identifier whatever its storage type and however many
    # times it repeats. A repeating `department_id` is a *foreign* key, and
    # summing or averaging it is meaningless either way.
    if _looks_like_identifier(name):
        return "identifier"

    if _is_numeric(dtype):
        # Low-cardinality numerics (a 1-5 rating, a year) stay numeric: users do
        # legitimately average a rating. Their distinct values are still
        # surfaced as `categories` below, so filtering works too.
        return "numeric"

    if distinct_count <= settings.categorical_max_cardinality:
        return "categorical"
    if nearly_unique:
        return "identifier"
    return "text"


def _scalar(session: Session, sql: str) -> Any:
    row = session.connection.execute(sql).fetchone()
    return row[0] if row else None


def profile_column(
    session: Session, table: str, column: str, dtype: str, row_count: int
) -> ColumnProfile:
    quoted = f'"{table}"."{column}"'
    null_count, distinct_count = session.connection.execute(
        f'SELECT count(*) FILTER (WHERE {quoted} IS NULL), '
        f'count(DISTINCT {quoted}) FROM "{table}"'
    ).fetchone()

    semantic_type = _classify(
        name=column, dtype=dtype, distinct_count=distinct_count, row_count=row_count
    )

    min_value = max_value = None
    if semantic_type in ("numeric", "temporal"):
        min_value, max_value = session.connection.execute(
            f'SELECT min({quoted}), max({quoted}) FROM "{table}"'
        ).fetchone()

    # For anything low-cardinality, hand over the *complete* value list. This is
    # what stops the model inventing 'Europe' when the data says 'EMEA' — and it
    # applies to numerics too, so "rating of 5" filters on a value that exists.
    categories = None
    if (
        semantic_type in ("categorical", "boolean", "numeric")
        and 0 < distinct_count <= settings.categorical_max_cardinality
    ):
        categories = [
            row[0]
            for row in session.connection.execute(
                f'SELECT DISTINCT {quoted} FROM "{table}" '
                f"WHERE {quoted} IS NOT NULL ORDER BY 1"
            ).fetchall()
        ]

    # Most-frequent values are more representative than an arbitrary head().
    sample_values = [
        row[0]
        for row in session.connection.execute(
            f'SELECT {quoted} FROM "{table}" WHERE {quoted} IS NOT NULL '
            f"GROUP BY 1 ORDER BY count(*) DESC LIMIT {settings.profile_sample_values}"
        ).fetchall()
    ]

    return ColumnProfile(
        name=column,
        original_name=session.column_labels.get(table, {}).get(column, column),
        dtype=dtype,
        semantic_type=semantic_type,
        null_count=null_count,
        null_fraction=round(null_count / row_count, 4) if row_count else 0.0,
        distinct_count=distinct_count,
        sample_values=sample_values,
        min_value=min_value,
        max_value=max_value,
        categories=categories,
    )


def profile_table(session: Session, table: str, source_file: str,
                  sheet_name: str | None = None) -> TableProfile:
    row_count = _scalar(session, f'SELECT count(*) FROM "{table}"') or 0

    columns_meta = session.connection.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()

    columns = [
        profile_column(session, table, name, dtype, row_count)
        for name, dtype in columns_meta
    ]

    return TableProfile(
        name=table,
        source_file=source_file,
        sheet_name=sheet_name,
        row_count=row_count,
        columns=columns,
    )
