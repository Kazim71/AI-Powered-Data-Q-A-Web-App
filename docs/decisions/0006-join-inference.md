# 0006 · Infer joins by measured value overlap

- **Status:** Accepted
- **Date:** 2026-09-17

## Context

Criterion #2 is cross-file analysis. Models write JOIN syntax fine; they fail at knowing
**which columns relate**, especially when names differ (`employees.department_id` vs
`departments.id`) or coincide on unrelated data.

## Options considered

| Option | For | Against |
|---|---|---|
| Let the LLM infer joins from column names | No code | Guesses; wrong joins produce silently wrong totals |
| Ask the user to define relationships | Always correct | Friction; users don't think in keys |
| **Name-based candidates, confirmed by measured overlap** | Grounded in the data; no user effort | Misses relationships with unrelated names |

## Decision

1. **Candidates** from identical names or the FK convention `<singular_table>_id ↔ id`.
2. **Reject degenerate keys**: < 2 distinct values, or a non-identifier with < 5.
3. **Measure overlap** in DuckDB — fraction of distinct left values present on the right,
   sampled to 1,000, computed both directions, higher kept.
4. **Emit hints** at ≥ 0.40 (`medium`) or ≥ 0.80 (`high`); discard the rest.

Hints go into the prompt as explicit statements, e.g.
`employees.department_id → departments.id (100% match)`.

## Consequences

**Positive**
- Joins are grounded in the data, not in naming luck.
- Coincidental name matches on unrelated values produce no hint.

**Negative / accepted risks**
- Step 2 was added **after testing surfaced a false positive**: `salaries_2023.currency ↔
  salaries_2024.currency` scored a perfect 1.0 because both are the constant `'INR'`.
  Overlap alone isn't enough; a key needs cardinality.
- Relationships with dissimilar names (`emp_no` ↔ `employee_id`) aren't found. Future: also
  test value overlap between identifier columns of compatible type regardless of name, bounded
  to keep the pair count manageable.
- Pairwise over tables: fine for the 10-table session cap, would need pruning beyond that.
