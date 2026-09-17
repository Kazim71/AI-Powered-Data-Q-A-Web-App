# 0005 · Classify columns by usage, not storage type

- **Status:** Accepted
- **Date:** 2026-09-17

## Context

A column's storage type says little about how it should be analysed. `employee_id` is a
`BIGINT`, but `SUM(employee_id)` is meaningless. A 1–5 `performance_rating` is a `DOUBLE`
with four distinct values — is it a measure or a category? The LLM needs this spelled out, or
it writes valid SQL that answers the wrong question.

## Options considered

| Option | For | Against |
|---|---|---|
| Physical dtype only | Free | Model sums IDs, averages codes |
| Ask the LLM to classify columns | Handles semantic nuance | Extra call per upload; non-deterministic; can't be tested |
| **Heuristics over name, dtype, and cardinality** | Deterministic, instant, testable | Occasional misses on unusual schemas |

## Decision

Six semantic types — `identifier`, `numeric`, `temporal`, `categorical`, `boolean`, `text` —
assigned by ordered heuristics (see [03 · Data pipeline](../03-data-pipeline.md#semantic-types)).

Two rules were **revised after testing against real sample data**:

1. **Id-like names are always `identifier`.** The first draft only did this for near-unique
   columns, so the foreign key `department_id` (5 values over 120 rows) became `categorical`.
   A foreign key repeats by nature; repetition doesn't make it a label.
2. **Low-cardinality numerics stay `numeric`.** The first draft demoted any numeric with ≤ 12
   distinct values to `categorical`, which would steer the model away from
   `AVG(performance_rating)` — one of the most natural questions to ask. Instead they remain
   `numeric` **and** expose their full value list as `categories`, so both averaging and
   exact filtering work.

## Consequences

- The prompt tells the model what not to aggregate.
- Classification is covered by tests pinned to the sample data.
- Heuristics can misfire on unusual schemas (e.g. a measure literally named `score_code`).
  Future: let the user override a column's type in the UI.
