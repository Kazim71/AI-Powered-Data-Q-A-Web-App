# 0001 · Answer questions by generating SQL for DuckDB

- **Status:** Accepted
- **Date:** 2026-09-17

## Context

Users ask analytical questions — totals, averages, filters, comparisons, trends — across one
or more uploaded files. The answer must be **correct**. An LLM that produces a plausible but
wrong number is worse than no answer, because the user can't tell.

## Options considered

| Option | For | Against |
|---|---|---|
| **A. Put the rows in the prompt** and let the LLM answer | Simplest possible | Context limits break past a few hundred rows; LLMs are unreliable at arithmetic; numbers can be hallucinated; no way to audit |
| **B. LLM writes pandas code, we `exec()` it** | Flexible; strong model familiarity | Arbitrary code execution on the server; sandboxing is real work; brittle across dtypes |
| **C. LLM writes SQL, DuckDB executes it** | Numbers computed by an engine; SQL is declarative and statically validatable; auditable | SQL can't express everything; model must know the schema well |
| D. Agent framework (LangChain SQL agent) | Batteries included | Heavy abstraction, multi-call loops, harder to debug in a 6-hour build |

## Decision

**Option C**, with DuckDB as the engine.

DuckDB specifically because it is in-process (no server), reads CSV natively and streams it,
and holds every uploaded file as a table in **one database — so cross-file JOINs need no
special handling at all.** It is also very fast on analytical queries.

## Consequences

**Positive**
- Answers are *computed*, not generated. The LLM decides what to compute; it never produces
  the number itself.
- Prompt size depends on schema width, not row count. A 1 M-row file costs the same tokens as
  a 10-row one, which is what makes a free open-weights model sufficient.
- The data itself never leaves the server — only the schema profile goes to the LLM.
- SQL can be parsed and validated **before** execution (see sqlglot guard, M2), and shown to
  the user for trust.

**Negative / accepted risks**
- Answer quality is bounded by how well the model understands the schema. Mitigated by
  profiling ([0005](0005-semantic-type-classification.md)) and join inference
  ([0006](0006-join-inference.md)).
- Some questions (forecasting, fuzzy text analysis) don't map to SQL. Acceptable: the brief's
  question types all do.
- Executing generated SQL requires guardrails: read-only statements only, row caps, timeouts.
