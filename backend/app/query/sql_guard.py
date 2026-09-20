"""Validates model-generated SQL before it ever reaches DuckDB.

This is the layer that makes "let an LLM write SQL against your data" safe
enough to ship. Two independent defences:

1. **Allow-list, not deny-list, on statement shape.** The parsed root must be
   a SELECT (optionally with CTEs) or a set operation over SELECTs. Anything
   else — INSERT, CREATE, ATTACH, PRAGMA, COPY, a second statement smuggled
   in after a semicolon — is rejected by construction, not by trying to
   enumerate every dangerous keyword.
2. **A function deny-list, defense in depth.** A bare SELECT can still read
   arbitrary files (`SELECT * FROM read_csv('/etc/passwd')`) or touch the
   system (`current_setting`, `getenv`) without ever using a forbidden
   statement type. These are blocked explicitly.

Column names are deliberately **not** exhaustively validated here — that
would mean re-implementing SQL name resolution (aliases, unqualified
references, expressions). Instead, table existence is checked strictly, and
a wrong column name is caught at execution time and handed to the one-shot
repair loop (see executor.py), which is both simpler and, since DuckDB's own
column-not-found errors are precise, just as effective in practice.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.core.errors import SQLGenerationError

DIALECT = "duckdb"

# Root node types we allow as the entire statement. Everything else — DDL,
# DML, PRAGMA/ATTACH/COPY/SET (which sqlglot mostly parses as exp.Command) —
# is rejected without needing to name each one.
_ALLOWED_ROOT_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)

# Table-valued functions and system/environment functions that would let a
# SELECT escape the uploaded tables entirely, even though the statement shape
# itself is an innocent-looking SELECT.
_FORBIDDEN_FUNCTIONS = {
    "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto",
    "read_ndjson", "read_ndjson_auto", "parquet_scan", "csv_scan", "json_scan",
    "sqlite_scan", "postgres_scan", "postgres_query", "mysql_scan", "iceberg_scan",
    "delta_scan", "glob", "getenv", "current_setting", "current_database",
    "pragma_database_list", "pragma_table_info", "duckdb_settings",
}


def _root_expression(parsed: exp.Expression) -> exp.Expression:
    return parsed


def _cte_names(root: exp.Expression) -> set[str]:
    with_clause = root.args.get("with")
    if not with_clause:
        return set()
    return {cte.alias_or_name.lower() for cte in with_clause.expressions}


def _used_function_names(root: exp.Expression) -> set[str]:
    names: set[str] = set()
    for node in root.walk():
        if isinstance(node, exp.Anonymous):
            names.add(str(node.this).lower())
        elif isinstance(node, exp.Func) and node.sql_name():
            names.add(node.sql_name().lower())
    return names


def _referenced_tables(root: exp.Expression, cte_names: set[str]) -> set[str]:
    tables = set()
    for table in root.find_all(exp.Table):
        name = table.name
        if name and name.lower() not in cte_names:
            tables.add(name)
    return tables


def _apply_row_cap(root: exp.Expression, cap: int) -> exp.Expression:
    """Ensure the statement can never return more than `cap` rows.

    Requests `cap + 1` rather than `cap` when a limit needs to be added, so
    the executor can tell "exactly `cap` rows exist" apart from "there were
    more and we cut it off" by checking whether that extra row came back —
    then trims to `cap` before it ever reaches the client. Never loosens a
    LIMIT the model already wrote that's within bounds (e.g. `LIMIT 5` stays
    `LIMIT 5`, with no truncation to signal).
    """
    existing = root.args.get("limit")
    if existing is not None:
        try:
            if int(existing.expression.this) <= cap:
                return root
        except (TypeError, ValueError, AttributeError):
            pass  # non-literal LIMIT expression: fall through and cap it
    return root.limit(cap + 1)


class ValidatedQuery:
    """A statement that passed the guard, ready to execute."""

    def __init__(self, sql: str, tables: set[str]) -> None:
        self.sql = sql
        self.tables = tables


def validate_sql(raw_sql: str, *, known_tables: set[str], row_cap: int) -> ValidatedQuery:
    """Parse, validate, and row-cap a model-generated SQL string.

    Raises SQLGenerationError with a message specific enough to feed straight
    back into the repair prompt.
    """
    raw_sql = raw_sql.strip().rstrip(";")
    if not raw_sql:
        raise SQLGenerationError("The model returned an empty SQL statement.")

    try:
        statements = sqlglot.parse(raw_sql, read=DIALECT)
    except sqlglot.errors.ParseError as exc:
        raise SQLGenerationError(
            "The generated SQL could not be parsed.", detail=str(exc)
        ) from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLGenerationError(
            f"Expected exactly one SQL statement, got {len(statements)}.",
            detail="Multiple statements (e.g. separated by ';') are not allowed.",
        )

    root = _root_expression(statements[0])
    if not isinstance(root, _ALLOWED_ROOT_TYPES):
        raise SQLGenerationError(
            f"Only SELECT queries are allowed; got a {type(root).__name__} statement.",
            detail="DDL, DML, and administrative statements (ATTACH/COPY/PRAGMA/SET) "
            "are not permitted.",
        )

    forbidden_used = _used_function_names(root) & _FORBIDDEN_FUNCTIONS
    if forbidden_used:
        raise SQLGenerationError(
            f"The query uses a disallowed function: {', '.join(sorted(forbidden_used))}.",
            detail="Only the uploaded tables may be read — no file, database, or "
            "system functions.",
        )

    cte_names = _cte_names(root)
    tables = _referenced_tables(root, cte_names)
    unknown = {t for t in tables if t not in known_tables}
    if unknown:
        raise SQLGenerationError(
            f"The query references a table that doesn't exist: {', '.join(sorted(unknown))}.",
            detail=f"Available tables: {', '.join(sorted(known_tables))}.",
        )

    capped = _apply_row_cap(root, row_cap)
    return ValidatedQuery(sql=capped.sql(dialect=DIALECT), tables=tables)
