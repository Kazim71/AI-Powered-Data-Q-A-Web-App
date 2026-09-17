# 02 · Architecture

## System diagram

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend — Next.js + Tailwind + shadcn/ui + Recharts        │  ⏳ milestone 3
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
│        └──▶ query/  (next)                                    │  ⏳ milestone 2
│               prompts.py   schema → prompt                    │
│               llm.py       Groq | Ollama                      │
│               sql_guard.py sqlglot validation + repair        │
│               charts.py    result shape → chart spec          │
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

## Request flow: ask *(milestone 2 — designed, not yet built)*

```
POST /api/sessions/{id}/ask  { question }
 ├─ load cached schema                          (no re-scan)
 ├─ LLM: schema + join hints + question → SQL
 ├─ sql_guard: parse with sqlglot
 │    ├─ must be a single SELECT / WITH
 │    └─ every table + column must exist
 ├─ execute in DuckDB with row cap + timeout
 ├─ on error → one repair round with the error message
 ├─ charts.pick(result)                         (deterministic)
 ├─ LLM: small result → one-sentence answer
 └─ { answer, sql, columns, rows, chart, tables_used }
```

## Why these components

| Component | Rationale | ADR |
|---|---|---|
| DuckDB | In-process, native CSV, cross-file JOINs free | [0001](decisions/0001-nl-to-sql-over-duckdb.md) |
| Groq / Llama 3.3 | Open-weights, free tier, fast; Ollama for offline | [0002](decisions/0002-open-weights-llm-via-groq.md) |
| Rule-based charts | Charts can't hallucinate | [0003](decisions/0003-rule-based-chart-selection.md) |
| Per-session DuckDB file | Isolation without tenancy logic | [0004](decisions/0004-session-model.md) |
| Semantic types | Stops the model summing an ID column | [0005](decisions/0005-semantic-type-classification.md) |
| Measured join inference | Cross-file correctness without guessing | [0006](decisions/0006-join-inference.md) |
