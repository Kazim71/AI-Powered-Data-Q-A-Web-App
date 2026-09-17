# Architecture Decision Records

Each record captures one significant decision: context, options, choice, and consequences.
Records are **append-only** — to change a decision, write a new ADR that supersedes the old
one and update the old one's status.

| # | Decision | Status |
|---|---|---|
| [0001](0001-nl-to-sql-over-duckdb.md) | Answer questions by generating SQL for DuckDB | Accepted |
| [0002](0002-open-weights-llm-via-groq.md) | Open-weights LLM via Groq, Ollama as offline fallback | Accepted |
| [0003](0003-rule-based-chart-selection.md) | Choose charts with rules, not the LLM | Accepted |
| [0004](0004-session-model.md) | Ephemeral per-session DuckDB files, in-process registry | Accepted |
| [0005](0005-semantic-type-classification.md) | Classify columns by usage, not storage type | Accepted |
| [0006](0006-join-inference.md) | Infer joins by measured value overlap | Accepted |

## Template

```markdown
# NNNN · Title

- **Status:** Proposed | Accepted | Superseded by NNNN
- **Date:** YYYY-MM-DD

## Context
## Options considered
## Decision
## Consequences
```
