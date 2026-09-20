"""Runs validated SQL against a session's DuckDB connection.

Two things this layer owns that sql_guard.py deliberately doesn't:

* **A real timeout.** DuckDB has no query-level timeout argument, so the
  query runs on a worker thread while this coroutine waits with
  `asyncio.wait_for`; on timeout, `connection.interrupt()` is called from the
  event-loop thread to cancel it. `interrupt()` is explicitly documented by
  DuckDB as safe to call from a different thread than the one running the
  query — that's its intended use.
* **Truncation detection.** sql_guard asks for `cap + 1` rows when it has to
  inject a LIMIT. Here that extra row is the signal: if it came back, the
  real result was larger than the cap, so `truncated=True` is set and the
  row is trimmed off before the client ever sees it.
"""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.errors import AppError
from app.core.session import Session


class QueryTimeout(AppError):
    status_code = 504


class QueryExecutionError(AppError):
    """The query parsed and passed validation but DuckDB rejected it.

    Distinct from SQLGenerationError (query/sql_guard.py) so the caller can
    tell "the guard rejected this before running it" apart from "DuckDB
    itself rejected it" — the latter is what should trigger the repair loop,
    since it's the case where the SQL was syntactically plausible but wrong
    in a way only the engine's own schema knowledge catches (e.g. a column
    name that doesn't exist).
    """

    status_code = 422


class QueryResult:
    def __init__(
        self, columns: list[str], rows: list[list[object]], truncated: bool
    ) -> None:
        self.columns = columns
        self.rows = rows
        self.truncated = truncated
        self.row_count = len(rows)


def _run_sync(session: Session, sql: str) -> tuple[list[str], list[tuple]]:
    cursor = session.connection.execute(sql)
    columns = [d[0] for d in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    return columns, rows


async def execute_query(
    session: Session,
    sql: str,
    *,
    row_cap: int | None = None,
    timeout_seconds: int | None = None,
) -> QueryResult:
    """Execute `sql` (already validated by sql_guard) and return its result.

    Raises QueryTimeout if it runs past `timeout_seconds`, or
    QueryExecutionError if DuckDB rejects it (wrong column name, type
    mismatch, etc.) — the caller decides whether to feed that back to the
    model for a repair attempt.
    """
    row_cap = row_cap if row_cap is not None else settings.max_result_rows
    timeout_seconds = (
        timeout_seconds if timeout_seconds is not None else settings.query_timeout_seconds
    )
    loop = asyncio.get_running_loop()

    try:
        columns, raw_rows = await asyncio.wait_for(
            loop.run_in_executor(None, _run_sync, session, sql),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        session.connection.interrupt()
        raise QueryTimeout(
            f"The query took longer than {timeout_seconds}s and was stopped.",
            detail="Try a narrower question, or one that touches fewer rows.",
        ) from exc
    except Exception as exc:  # DuckDB raises a family of its own error types
        raise QueryExecutionError(
            "The database rejected the generated SQL.", detail=str(exc)
        ) from exc

    truncated = len(raw_rows) > row_cap
    if truncated:
        raw_rows = raw_rows[:row_cap]

    rows = [list(row) for row in raw_rows]
    return QueryResult(columns=columns, rows=rows, truncated=truncated)
