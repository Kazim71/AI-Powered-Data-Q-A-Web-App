"""Orchestrates one `/ask` request end to end.

    question -> LLM (SQL) -> guard -> execute -> [repair once on failure]
             -> chart (rules) -> LLM (one-sentence answer) -> AskResponse

This is the only module that calls the other query/* pieces together; each of
them stays independently testable (prompts.py has no network calls,
sql_guard.py has no LLM or DuckDB, charts.py is a pure function, executor.py
takes already-validated SQL). Kept as plain functions, not a class — there's
no state to hold between calls.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.errors import EmptySession, LLMError, SQLGenerationError
from app.core.session import Session
from app.ingestion.catalog import get_schema
from app.models import AskResponse, SessionSchema
from app.query import prompts
from app.query.charts import pick_chart
from app.query.executor import QueryExecutionError, QueryResult, QueryTimeout, execute_query
from app.query.llm import LLMClient, get_llm_client
from app.query.sql_guard import ValidatedQuery, validate_sql

logger = logging.getLogger("app.query")


def _parse_sql_response(payload: dict) -> tuple[str, list[str]]:
    sql = payload.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise SQLGenerationError(
            "The model's response did not include a SQL statement.",
            detail=str(payload)[:500],
        )
    assumptions = payload.get("assumptions") or []
    if not isinstance(assumptions, list):
        assumptions = [str(assumptions)]
    return sql, [str(a) for a in assumptions]


async def _generate_and_run(
    llm: LLMClient,
    session: Session,
    schema: SessionSchema,
    question: str,
    known_tables: set[str],
) -> tuple[ValidatedQuery, QueryResult, list[str], bool]:
    """Generate SQL, validate, and execute — with one self-repair round trip.

    Returns (validated_query, result, assumptions, repaired). Raises
    SQLGenerationError / QueryTimeout if even the repaired attempt fails.
    """
    system, user = prompts.build_sql_generation_prompt(schema, question)
    payload = await llm.complete_json(
        system=system, user=user, temperature=settings.llm_temperature_sql
    )
    sql, assumptions = _parse_sql_response(payload)

    last_error: Exception | None = None
    for attempt in range(settings.sql_repair_attempts + 1):
        try:
            validated = validate_sql(
                sql, known_tables=known_tables, row_cap=settings.max_result_rows
            )
            result = await execute_query(session, validated.sql)
            return validated, result, assumptions, attempt > 0
        except (SQLGenerationError, QueryExecutionError, QueryTimeout) as exc:
            last_error = exc
            if attempt >= settings.sql_repair_attempts:
                break
            logger.info("SQL attempt %d failed, repairing: %s", attempt + 1, exc.message)
            repair_system, repair_user = prompts.build_sql_repair_prompt(
                schema, question, sql, exc.message
            )
            payload = await llm.complete_json(
                system=repair_system, user=repair_user,
                temperature=settings.llm_temperature_sql,
            )
            sql, repaired_assumptions = _parse_sql_response(payload)
            assumptions = repaired_assumptions or assumptions

    assert last_error is not None
    if isinstance(last_error, QueryTimeout):
        raise last_error
    raise SQLGenerationError(
        "Could not produce a working query for this question, even after one retry.",
        detail=last_error.message,
    )


async def answer_question(session: Session, question: str) -> AskResponse:
    schema = get_schema(session)
    if not schema.tables:
        raise EmptySession(
            "Upload at least one file before asking a question."
        )
    known_tables = {t.name for t in schema.tables}

    llm = get_llm_client()
    validated, result, assumptions, repaired = await _generate_and_run(
        llm, session, schema, question, known_tables
    )

    chart = pick_chart(result.columns, result.rows)

    answer_text = await _summarise(llm, question, result)

    return AskResponse(
        answer=answer_text,
        sql=validated.sql,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        chart=chart,
        tables_used=sorted(validated.tables),
        repaired=repaired,
        assumptions=assumptions,
    )


async def _summarise(llm: LLMClient, question: str, result: QueryResult) -> str:
    """Turn the result into one plain-English sentence.

    A failure here (rate limit, timeout) shouldn't discard a query that
    already succeeded — fall back to a plain, honest description instead of
    failing the whole request.
    """
    if result.row_count == 0:
        return "No matching data was found for this question."

    try:
        system, user = prompts.build_answer_summary_prompt(
            question, result.columns, result.rows
        )
        payload = await llm.complete_json(
            system=system, user=user, temperature=settings.llm_temperature_summary
        )
        answer = payload.get("answer")
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
    except LLMError as exc:
        logger.info("Answer summary call failed, falling back: %s", exc.message)

    noun = "row" if result.row_count == 1 else "rows"
    return f"Returned {result.row_count} {noun} across {len(result.columns)} column(s)."
