# 03 · Data pipeline

How a file on the user's disk becomes a queryable, well-described table. This pipeline is
the foundation of answer quality: the LLM can only write correct SQL against a schema it
understands.

Code: `backend/app/ingestion/`

---

## Stage 1 · Loading — `loader.py`

| Format | Reader | Why |
|---|---|---|
| `.csv` `.tsv` `.txt` | DuckDB `read_csv_auto` | Streams (never fully in memory), sniffs delimiter/encoding, better type inference than a plain pandas read |
| `.xlsx` `.xls` `.xlsm` | pandas + openpyxl | DuckDB has no first-class Excel reader |

**Rules**
- **Each Excel sheet becomes its own table.** A workbook is a collection of datasets;
  flattening it loses structure. Blank sheets are skipped.
- **Name collisions never clobber.** Uploading `data.csv` twice yields `data` and `data_2`.
- **Partial success.** A bad file reports `status: failed` with a reason; the other files in
  the batch still load.
- Uploads stream to disk in 1 MB chunks and abort the moment they cross the size cap.

`load_file` returns `LoadedTable(table, source_file, sheet_name)` so provenance travels with
the table rather than being reverse-engineered from its name.

---

## Stage 2 · Naming — `naming.py`

Real headers look like `Total Revenue (₹)`, `  employee id `, `2024 Q1`, or two columns both
named `Notes`. SQL needs stable, unquoted, unique identifiers.

| Raw header | Normalised | Rule |
|---|---|---|
| `Employee ID` | `employee_id` | lowercase, non-alphanumerics → `_` |
| `Total Revenue (₹)` | `total_revenue` | unicode folded to ASCII, symbols dropped |
| `Café Sales` | `cafe_sales` | accents stripped |
| `2024 Q1` | `c_2024_q1` | identifiers can't start with a digit |
| `select` | `select_col` | reserved words suffixed |
| `Notes`, `notes` | `notes`, `notes_2` | deduplicated in order |

**Originals are preserved.** Each table keeps a `{clean: original}` map, surfaced as
`original_name` on every column, so the UI shows the user their own header.

Renames happen in **two passes via placeholder names** (`__tmp_0` …) so a rename can never
collide with a column that hasn't been renamed yet.

Table names: `Q1 Sales.xlsx` + sheet `By Region` → `q1_sales_by_region`. A digit-only sheet
like `2023` gives `salaries_2023` — the `c_` guard is dropped because a suffix is already safe.

---

## Stage 3 · Profiling — `profiler.py`

**This is the most important stage for answer quality.** A bare column list tells a model
almost nothing; a profile tells it how each column should be used.

For every column, computed with SQL aggregates inside DuckDB (no rows pulled into Python):

| Field | Purpose for the LLM |
|---|---|
| `dtype` | Physical type |
| `semantic_type` | **How to use it** — see below |
| `null_fraction` | Warns about sparse columns |
| `distinct_count` | Cardinality |
| `sample_values` | Top-5 *most frequent* values (more representative than `head()`) |
| `min_value` / `max_value` | Numeric and date ranges → correct date filters |
| `categories` | **Complete** value list when cardinality ≤ 25 |

### Semantic types

| Type | Meaning | Example |
|---|---|---|
| `identifier` | A key. **Never aggregate.** | `employee_id`, `department_id` |
| `numeric` | A measure. Sum / average freely. | `base_salary_inr`, `performance_rating` |
| `temporal` | Dates and times. Group by period, filter by range. | `hire_date` |
| `categorical` | Low-cardinality label. Group and filter. | `level`, `location` |
| `boolean` | True/false flag. | `is_active` |
| `text` | High-cardinality free text. | `full_name` |

Classification order (first match wins):
1. Boolean dtype → `boolean`
2. Date/time dtype → `temporal`
3. **Id-like name** (`id`, `*_id`, `*_code`, `*_key`, …) → `identifier`, *regardless of type
   or repetition*
4. Numeric dtype → `numeric`
5. ≤ 25 distinct → `categorical`
6. ≥ 95% unique → `identifier`
7. Otherwise → `text`

Rationale and rejected alternatives: [ADR-0005](decisions/0005-semantic-type-classification.md).

### Why `categories` matters

When a user asks for "sales in Europe" and the data says `EMEA`, a model without the value
list invents `WHERE region = 'Europe'` and returns zero rows — a silently wrong answer. With
the complete list in the prompt, it picks `EMEA`. This applies to low-cardinality **numerics**
too: `performance_rating` stays `numeric` (so it can be averaged) but still exposes
`[2.0, 3.0, 4.0, 5.0]`.

---

## Stage 4 · Join inference — `joins.py`

Cross-file analysis rarely fails because the model can't write a JOIN. It fails because the
model doesn't know **which columns relate**. So we measure it.

**Step 1 — candidate pairs** (cheap, name-based):
- Identical column names across tables: `employees.employee_id` ↔ `salaries_2023.employee_id`
- Foreign-key convention: `employees.department_id` ↔ `departments.id`
  (table name singularised: `departments` → `department`)

**Step 2 — filter degenerate keys.** A column is rejected as a key if it has < 2 distinct
values, or is a non-identifier with < 5. Without this, a constant `currency = 'INR'` in two
tables reports a perfect 100% "relationship".

**Step 3 — measure value overlap** in DuckDB: the fraction of distinct left values found in
the right column, sampled to 1,000 values, computed **in both directions** and the higher
kept (a fact→dimension link is total one way, partial the other).

| Overlap | Confidence |
|---|---|
| ≥ 0.80 | `high` |
| 0.40 – 0.80 | `medium` |
| < 0.40 | discarded |

A name match on unrelated values produces no hint. Details:
[ADR-0006](decisions/0006-join-inference.md).

---

## Stage 5 · Catalogue — `catalog.py`

Assembles profiles + join hints into a `SessionSchema` and **caches it per session**.
Rebuilt once after each upload batch. `GET /schema` and the future `/ask` read the cache, so
asking a question never re-scans the data (measured: ~2.5 ms for a cached schema read).

---

## Verified output on sample data

Uploading `employees.csv`, `departments.csv`, `salaries.xlsx` (2 sheets):

```
TABLES  departments (5) · employees (120) · salaries_2023 (120) · salaries_2024 (120)

JOINS   departments.id            ↔ employees.department_id      1.0  high
        employees.employee_id     ↔ salaries_2023.employee_id    1.0  high
        employees.employee_id     ↔ salaries_2024.employee_id    1.0  high
        salaries_2023.employee_id ↔ salaries_2024.employee_id    1.0  high
```
