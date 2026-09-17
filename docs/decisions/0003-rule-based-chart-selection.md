# 0003 · Choose charts with rules, not the LLM

- **Status:** Accepted *(implementation: milestone 2)*
- **Date:** 2026-09-17

## Context

Criterion #3: render charts "where the question calls for one". The common approach is to ask
the LLM to also emit a chart spec. But the LLM writes its chart spec **before** it has seen
the result — it may pick a line chart for a single number, or a bar chart with 400 bars.

## Options considered

| Option | For | Against |
|---|---|---|
| LLM emits chart spec with the SQL | One call | Decided blind to the result; can reference columns that don't exist in the output |
| LLM picks chart in a second call after seeing results | Informed | Extra latency and cost; still non-deterministic |
| **Rules over the result set's shape** | Deterministic, instant, testable, can't hallucinate | Less "creative" |

## Decision

**A deterministic rule engine** inspects the executed result — column count, semantic types,
row count — and picks the chart.

| Result shape | Chart |
|---|---|
| 1 row × 1 numeric column | KPI card |
| 1 temporal + ≥ 1 numeric | Line |
| 1 categorical + 1 numeric, ≤ 8 rows, parts of a whole | Pie / donut |
| 1 categorical + ≥ 1 numeric, ≤ 30 rows | Bar |
| 2 numerics | Scatter |
| > 30 categories, or anything else | Table only |

The LLM may optionally pass a *hint* (e.g. the user said "pie chart"); rules honour it only
when the result shape supports it.

## Consequences

- Charts always match the data they display.
- Fully unit-testable with fixed result sets — no LLM in the loop.
- Some results a human would chart creatively will fall back to a table. Acceptable.
