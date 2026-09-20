# 02 · Architecture

## System diagram

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend — Next.js + TypeScript + Tailwind v4 + Recharts    │  ✅
│  Upload zone · Chat · Result table · Chart · SQL panel       │
└──────────────────────────────┬───────────────────────────────┘
                               │  REST / JSON + multipart
┌──────────────────────────────▼───────────────────────────────┐
│  Backend — FastAPI                                            │
│                                                               │
│   api/routes.py ── thin HTTP layer                            │
│        │                                                      │
│        ├──▶ core/session.py      session registry, DuckDB     │  ✅
│        │                                                      │
│        ├──▶ ingestion/                                        │  ✅
│        │      loader.py    files → tables                     │
│        │      naming.py    header normalisation               │
│        │      profiler.py  column profiles                    │
│        │      joins.py     relationship inference             │
│        │      catalog.py   builds + caches the schema         │
│        │                                                      │
│        └──▶ query/                                            │  ✅
│               prompts.py   schema → prompt                    │
│               llm.py       Groq | Ollama                      │
│               sql_guard.py sqlglot validation                 │
│               executor.py  timeout, row cap, truncation        │
│               charts.py    result shape → chart spec          │
│               service.py   orchestrates ask end to end         │
│                                                               │
│   ┌────────────────────────────────────────────┐              │
│   │ .sessions/<id>/uploads/   raw files        │              │
│   │ .sessions/<id>/data.duckdb  tables         │              │
│   └────────────────────────────────────────────┘              │
└───────────────────────────────────────────────────────────────┘
```

## Layering rules

These keep the codebase scalable as features land:

1. **`api/` is thin.** It validates, delegates, shapes the response. No business logic.
2. **`ingestion/` and `query/` know nothing about HTTP.** They raise domain errors from
   `core/errors.py`; `main.py` maps those to status codes. So every layer is unit-testable
   without an app.
3. **`models.py` is the contract.** Pydantic models are shared by the API *and* rendered into
   the LLM prompt. Changing a field there is an interface change.
4. **Dependencies point inward:** `api → ingestion/query → core`. Never the reverse.

## Request flow: upload

```
POST /api/sessions/{id}/files   (multipart, N files)
 │
 ├─ for each file:
 │    ├─ check extension                    → UnsupportedFileType (per-file, non-fatal)
 │    ├─ stream to disk in 1 MB chunks      → FileTooLarge, aborts early
 │    ├─ loader.load_file
 │    │    ├─ CSV:   DuckDB read_csv_auto   (streams, sniffs types)
 │    │    └─ Excel: pandas, one table per non-empty sheet
 │    ├─ normalise column names, keep originals
 │    └─ record provenance (source file, sheet)
 │
 └─ once, after all files:
      catalog.build_schema
        ├─ profile every table     (SQL aggregates, one scan per column)
        └─ infer joins             (name candidates → measured value overlap)
      → cached on the session
```

Profiling runs **once after the batch**, not per file, so join inference always sees the
complete set of tables.

## Request flow: ask

```
POST /api/sessions/{id}/ask  { question }
 ├─ load cached schema                          (no re-scan)
 ├─ reject if the session has no tables          → EmptySession, 400
 │
 ├─ LLM: schema + join hints + question → {sql, assumptions}   (JSON, temperature 0)
 │
 ├─ sql_guard.validate_sql                       (pure, no I/O)
 │    ├─ parse with sqlglot; exactly one statement
 │    ├─ root must be SELECT/WITH/set-op — allow-list, not a keyword deny-list
 │    ├─ reject filesystem/system functions (read_csv, getenv, ...)
 │    ├─ every referenced table must be in the session's real tables
 │    └─ inject/tighten LIMIT to row_cap + 1 (the +1 signals truncation)
 │
 ├─ executor.execute_query                       (async, DuckDB on a worker thread)
 │    ├─ asyncio.wait_for(..., timeout) → interrupt() the connection on timeout
 │    └─ trim the extra row, set `truncated`
 │
 ├─ on SQLGenerationError / QueryExecutionError / QueryTimeout:
 │    └─ ONE repair round — feed the exact error back to the LLM, retry the
 │       three steps above once more; still failing → 422/504, no more retries
 │
 ├─ charts.pick_chart(result)                    (pure function, no LLM)
 ├─ LLM: question + small result → {"answer": "..."}   (temperature 0.3)
 │    └─ on failure, fall back to a plain "Returned N rows..." — a flaky
 │       summary call never discards a query that already succeeded
 │
 └─ AskResponse { answer, sql, columns, rows, row_count, truncated,
                  chart, tables_used, repaired, assumptions }
```

Code: `backend/app/query/` — `prompts.py` (pure string building), `llm.py` (Groq/Ollama behind
one interface), `sql_guard.py` (pure validation), `executor.py` (DuckDB + timeout), `charts.py`
(pure function), `service.py` (orchestrates the above; the only module that calls them together).

## Why these components

| Component | Rationale | ADR |
|---|---|---|
| DuckDB | In-process, native CSV, cross-file JOINs free | [0001](decisions/0001-nl-to-sql-over-duckdb.md) |
| Groq (open-weights model) | Free tier, fast; Ollama for offline | [0002](decisions/0002-open-weights-llm-via-groq.md) |
| Rule-based charts | Charts can't hallucinate | [0003](decisions/0003-rule-based-chart-selection.md) |
| Per-session DuckDB file | Isolation without tenancy logic | [0004](decisions/0004-session-model.md) |
| Semantic types | Stops the model summing an ID column | [0005](decisions/0005-semantic-type-classification.md) |
| Measured join inference | Cross-file correctness without guessing | [0006](decisions/0006-join-inference.md) |
