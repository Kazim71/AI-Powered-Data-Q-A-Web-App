# 01 · Overview

## The brief

Darwinbox Forward Deployed Engineer take-home: build a small web app where a user uploads one
or more CSV/Excel files and asks analytical questions in plain English, getting back a clear,
correct answer. Budget: 4–6 focused hours. Open-source AI models required.

The brief states the evaluation explicitly: **scoping an ambiguous problem, making sound
decisions under constraints, and using AI tools to reach a working prototype** — not
hand-written code volume.

## Scope

**In scope**
- Multi-file CSV / TSV / Excel upload per session; each Excel sheet becomes its own table
- Natural-language questions answered via generated, validated SQL
- Cross-file joins
- Automatic chart selection
- Full transparency: the SQL behind every answer is visible

**Deliberately out of scope** (see [08 · Roadmap](08-roadmap.md) for when they'd matter)
- Authentication and multi-user tenancy
- Persistent sessions beyond a TTL
- Conversation memory / follow-up questions
- Writing back to or editing data

## Acceptance criteria → how they're met

| # | Criterion | Approach | Status |
|---|---|---|---|
| 1 | Multi-file upload | `POST /sessions/{id}/files` accepts many files; per-file status so one bad file doesn't fail the batch | ✅ Built |
| 2 | Cross-file analysis | Every file is a DuckDB table in one database, so JOINs are native. Join keys are **inferred and measured**, not guessed by the LLM | ✅ Joins inferred · ⏳ NL→SQL next |
| 3 | Visual insights | Rule engine picks chart type from the *shape of the result set* | ⏳ Milestone 2 |
| 4 | Delta solutioning on top of AI | Column profiling, join inference, SQL guardrails + repair loop, deterministic charts, SQL transparency | 🟡 2 of 5 built |

## The core idea in one paragraph

The LLM never sees the data — only a **profile** of it. It writes SQL; DuckDB computes the
answer. That means numbers are computed, not generated, so they can't be hallucinated; prompt
size is constant regardless of file size, so a free open-weights model is enough; and every
answer is auditable. Everything else in the system exists to make that SQL correct the first
time. See [ADR-0001](decisions/0001-nl-to-sql-over-duckdb.md).
