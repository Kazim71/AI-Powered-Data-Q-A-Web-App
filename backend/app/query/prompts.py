"""Renders a SessionSchema into the text the LLM actually sees.

This is the other half of the profiling investment (see ingestion/profiler.py):
profiling computes the facts, this module decides how to say them so a 70B
open-weights model writes correct DuckDB SQL on the first try.

Two prompts are built here:
  * SQL generation  — schema + join hints + question -> {sql, assumptions}
  * Answer summary  — question + a small result set -> one plain sentence

Both ask for strict JSON back, parsed defensively in llm.py, so this module
stays a pure string-building layer with no network or parsing concerns.
"""

from __future__ import annotations

import json

from app.models import ColumnProfile, JoinHint, SessionSchema, TableProfile

SQL_SYSTEM_PROMPT = """You are a meticulous data analyst who writes DuckDB SQL.

Given a database schema and a question in plain English, output a single JSON object:
{"sql": "<one SQL statement>", "assumptions": ["<short clause>", ...]}

Rules, in order of importance:
1. Output ONLY that JSON object. No markdown fences, no prose before or after.
2. The SQL must be exactly one statement: a SELECT, or a WITH ... SELECT. Never DDL
   (CREATE/ALTER/DROP), never DML (INSERT/UPDATE/DELETE), never multiple statements.
3. Use only the tables and columns given below, spelled exactly as given. Never invent a
   column or table name.
4. Never aggregate (SUM, AVG, etc.) a column marked (identifier) — it is a key, not a measure.
5. When filtering a column that lists its possible "values", use one of those values verbatim
   — do not guess a different spelling or synonym.
6. For a question spanning more than one table, join using the relationships given below.
   Do not invent a join key that isn't listed.
7. If the question is genuinely ambiguous (e.g. "top" performers with no metric named,
   a relative time period with no anchor date), pick the single most reasonable
   interpretation, apply it, and record it as one short clause per assumption
   (e.g. "interpreting 'top' as highest total_sales"). Leave "assumptions" as an empty
   list when the question is unambiguous — do not invent caveats for their own sake.
8. Always add a LIMIT to queries that could return an unbounded number of rows (e.g. row-level
   listings). Aggregations that naturally return few rows don't need one.
9. Prefer clear column aliases in the SELECT list (e.g. `AVG(x) AS avg_x`) so results are
   self-describing."""

REPAIR_SYSTEM_PROMPT = """You are a meticulous data analyst who writes DuckDB SQL.

Your previous SQL failed to execute. You are given the schema, the original question, the SQL
you wrote, and the exact database error. Fix it.

Output ONLY a JSON object: {"sql": "<corrected single SQL statement>", "assumptions": [...]}
Follow the same rules as before: one statement, only listed tables/columns, no DDL/DML."""

ANSWER_SYSTEM_PROMPT = """You turn a query result into a short, plain-English answer.

You will be given the user's question and the resulting data (as column names and rows).
Reply with ONLY a JSON object: {"answer": "<one or two sentences>"}

Rules:
- State the actual answer with its real numbers from the data. Never say "the data shows" —
  just answer.
- If the result is empty, say plainly that no matching data was found; do not guess why.
- Do not describe the SQL or the method. Do not add caveats unless the data is empty.
- Format numbers readably (e.g. "₹28.4L" or "1,234" rather than a raw float with many
  decimals) when the column name suggests currency, counts, or percentages."""


def _format_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _describe_column(column: ColumnProfile) -> str:
    parts = [f"{column.name} ({column.semantic_type}, {column.dtype}"]
    if column.null_fraction > 0:
        parts[0] += f", {column.null_fraction:.0%} null"
    parts[0] += ")"

    if column.categories is not None:
        values = ", ".join(_format_value(v) for v in column.categories)
        parts.append(f"values: {values}")
    elif column.min_value is not None:
        parts.append(f"range: {_format_value(column.min_value)} to {_format_value(column.max_value)}")
    elif column.sample_values:
        values = ", ".join(_format_value(v) for v in column.sample_values[:3])
        parts.append(f"e.g. {values}")

    return " — ".join(parts)


def _describe_table(table: TableProfile) -> str:
    lines = [f"### {table.name} ({table.row_count} rows)"]
    lines += [f"- {_describe_column(c)}" for c in table.columns]
    return "\n".join(lines)


def _describe_joins(join_hints: list[JoinHint]) -> str:
    if not join_hints:
        return "(none detected — if the question needs more than one table, look for " \
               "columns with matching names and use your judgement)"
    lines = []
    for hint in join_hints:
        pct = f"{hint.overlap:.0%}"
        lines.append(
            f"- {hint.left_table}.{hint.left_column} = "
            f"{hint.right_table}.{hint.right_column}  ({pct} value match, {hint.confidence} confidence)"
        )
    return "\n".join(lines)


def build_schema_context(schema: SessionSchema) -> str:
    """The shared schema block used by both the generation and repair prompts."""
    tables_block = "\n\n".join(_describe_table(t) for t in schema.tables)
    joins_block = _describe_joins(schema.join_hints)
    return (
        "## Tables\n\n"
        f"{tables_block}\n\n"
        "## Relationships (verified against the actual data, not just column names)\n\n"
        f"{joins_block}"
    )


def build_sql_generation_prompt(schema: SessionSchema, question: str) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for the initial SQL generation call."""
    user_prompt = f"{build_schema_context(schema)}\n\n## Question\n\n{question}"
    return SQL_SYSTEM_PROMPT, user_prompt


def build_sql_repair_prompt(
    schema: SessionSchema, question: str, failed_sql: str, error_message: str
) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for the one-shot repair call."""
    user_prompt = (
        f"{build_schema_context(schema)}\n\n"
        f"## Question\n\n{question}\n\n"
        f"## Your previous SQL\n\n{failed_sql}\n\n"
        f"## Database error\n\n{error_message}"
    )
    return REPAIR_SYSTEM_PROMPT, user_prompt


# Cap on how much result data goes into the summary prompt. The chat answer
# only needs to *describe* the result, not reproduce it — and a huge result
# means the row cap already truncated it, so length here is inherently bounded
# by max_result_rows but we cap again defensively for wide/text-heavy tables.
_SUMMARY_MAX_ROWS = 30
_SUMMARY_MAX_CHARS = 4000


def build_answer_summary_prompt(
    question: str, columns: list[str], rows: list[list[object]]
) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for the result -> sentence call."""
    preview_rows = rows[:_SUMMARY_MAX_ROWS]
    payload = json.dumps({"columns": columns, "rows": preview_rows}, default=str)
    if len(payload) > _SUMMARY_MAX_CHARS:
        payload = payload[:_SUMMARY_MAX_CHARS] + "...(truncated)"

    note = "" if len(rows) <= _SUMMARY_MAX_ROWS else f"\n\n({len(rows)} rows total, showing first {_SUMMARY_MAX_ROWS})"
    user_prompt = f"## Question\n\n{question}\n\n## Result\n\n{payload}{note}"
    return ANSWER_SYSTEM_PROMPT, user_prompt
