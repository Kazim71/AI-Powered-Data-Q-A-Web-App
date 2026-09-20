# 10 · Project overview

*A self-contained write-up for review/presentation. For the deep-dive versions of anything
here, see the linked docs — this page is the map, not the territory.*

---

## What it is

A web app where you upload one or more CSV/Excel files and ask questions about them in plain
English — totals, averages, filters, comparisons, trends, across files — and get back a
correct answer, a chart when one makes sense, and the exact SQL that produced it.

**Live:**
- App: `https://ai-powered-data-q-a-web-app.vercel.app`
- API: `https://ai-powered-data-q-a-web-app.onrender.com/api/health`
- Repo: `https://github.com/Kazim71/AI-Powered-Data-Q-A-Web-App`

## The problem

The brief (Darwinbox, Forward Deployed Engineer take-home): build this in 4–6 hours, using
open-source AI models, and be evaluated on **how you scope an ambiguous problem and make sound
decisions under constraints** — not on hand-written code volume. Four acceptance criteria:
multi-file upload, cross-file analysis, visual insights, and "delta solutioning on top of what
AI does."

That last one is the real ask, and it's the thread this whole project pulls on: an LLM alone,
handed a spreadsheet and a question, is unreliable — it hallucinates numbers, can't reliably do
arithmetic at scale, and has no way to prove its answer is right. The interesting engineering
problem isn't "call an LLM," it's "what do you build *around* the LLM so its output is
trustworthy."

## The core idea

**The LLM never sees your data — only a profile of it. It writes SQL; a real database computes
the answer.**

```
files ──▶ normalise ──▶ profile columns ──▶ infer joins ──▶ cached schema
                                                                 │
question ──▶ open-weights LLM ──▶ SQL ──▶ validate ──▶ execute ──▶ answer + chart + SQL
                     ▲                        │
                     └────── repair once ─────┘  (on validation or execution failure)
```

Every uploaded file becomes a table in an embedded [DuckDB](https://duckdb.org) database — a
real analytical SQL engine, running in-process, not a separate server. The model's only job is
translating "average base salary by department in 2024?" into a `SELECT` statement against a
description of the schema. DuckDB executes it and returns the real number.

This one architectural choice resolves most of the brief's hard parts at once:

| Consequence | Why it matters |
|---|---|
| Numbers are **computed**, not generated | The model can't hallucinate a total — it can only write a wrong query, which is visible and checkable |
| Multi-file JOINs are native | Every file lands in one database; cross-file analysis (criterion #2) needs no special-casing |
| Prompt size is constant regardless of file size | A 10-row file and a 1M-row file cost the same tokens — a free-tier model is genuinely sufficient |
| The answer is auditable | Every response ships with the exact SQL that produced it, and the tables it touched |

Full reasoning and the alternatives rejected (stuffing rows into the prompt; letting the model
write and `exec()` pandas): [ADR-0001](decisions/0001-nl-to-sql-over-duckdb.md).

## How it works

### 1. Upload → schema

```
POST /sessions/{id}/files
 → each file becomes one or more DuckDB tables (each Excel sheet is its own table)
 → column headers normalised to safe SQL identifiers ("Base Salary (INR)" → base_salary_inr),
   original headers preserved for display
 → every column profiled: semantic type (identifier/numeric/temporal/categorical/boolean/text),
   null %, cardinality, value ranges, and — for low-cardinality columns — the complete list of
   real values
 → relationships between files inferred by measuring actual value overlap between candidate
   columns (not just matching names), so a JOIN key is a verified fact, not a guess
```
Detail: [03 · Data pipeline](03-data-pipeline.md).

### 2. Question → answer

```
POST /sessions/{id}/ask  { "question": "..." }
 → LLM: schema profile + verified join hints + question → { sql, assumptions }
 → guard: parse the SQL; the statement must BE a SELECT (allow-list on shape, not a keyword
   deny-list) + a function deny-list against reading outside the uploaded tables + every table
   must exist in this session
 → execute in DuckDB, with a real timeout and a row cap
 → on failure (bad SQL, DB error): ONE repair round-trip — the exact error goes back to the
   model, one retry, then a clear failure if it still doesn't work
 → chart picked by rules over the RESULT's shape (not by the LLM, which writes SQL before
   seeing what comes back) — KPI / line / bar / pie / scatter / plain table
 → a second, small LLM call turns the result into one plain sentence; if that call fails, a
   plain "returned N rows" fallback is used instead of discarding an already-correct answer
```
Detail: [02 · Architecture](02-architecture.md#request-flow-ask).

## Why this stack (and not the obvious alternatives)

| Layer | Chosen | Rejected alternative | Why |
|---|---|---|---|
| Analytics engine | **DuckDB**, embedded | Postgres/SQLite as a separate service | No server to host, no connection pooling, native CSV/Excel-adjacent ingestion, and a database *is* the point — see above |
| Answering strategy | **LLM writes SQL, DB executes it** | LLM reads rows directly; LLM writes & runs pandas | Rows-in-prompt breaks past a few hundred rows and can't do reliable arithmetic; `exec()`-ing model-written Python is a real code-execution risk for negligible gain over SQL |
| LLM | **Groq-hosted `openai/gpt-oss-120b`**, open-weights (Apache 2.0) | A closed model (GPT-4/Claude/Gemini) | The brief requires open-source models; Groq's free tier is fast enough to feel responsive, and the model is genuinely strong at SQL |
| LLM fallback | **Ollama**, same interface | — | A real "runs fully on-prem, no data or schema leaves the machine" story — relevant for an HR-adjacent product where that matters |
| SQL safety | **Allow-list on statement shape** + function deny-list | Enumerate forbidden keywords (`DROP`, `DELETE`, ...) | A deny-list is an open-ended list you keep discovering gaps in; asserting the parsed root *is* a `SELECT` rejects everything else by construction |
| Chart selection | **Rules over the executed result's shape** | Ask the LLM to also emit a chart spec | The model would be choosing blind, before it's seen what the query returns — a bar chart with 400 bars, a line chart for one number |
| Backend | **FastAPI (Python)** | Node/Express | DuckDB, pandas, and the whole data-tooling ecosystem live in Python; async support is native for the timeout/cancellation work in query execution |
| Frontend | **Next.js + TypeScript + Tailwind v4** | A no-code/low-code builder | Full control over the state machine (upload → profiling → asking → repair → chart), which a builder abstracts away right when precision matters most |
| Session storage | **Per-session DuckDB file on disk, in-process registry** | Postgres + Redis | Zero extra infra for a prototype; complete data isolation between users for free; the accepted trade-off (single-instance only) is [documented, not hidden](decisions/0004-session-model.md) |
| Hosting | **Render (API) + Vercel (web)** | A self-managed VPS | Both free forever at this scale, zero ops for the deadline. Render's cold start and Oracle Cloud's free-VM alternative (no cold start, more setup) are both written up in [06 · Deployment](06-deployment.md) for when that trade-off matters |

## The "delta solutioning" (criterion #4) — five things layered around the raw LLM call

1. **Column profiling before prompting** — semantic types stop the model summing an ID column;
   full value lists for low-cardinality columns stop it inventing `'Europe'` when the data says
   `'EMEA'`. [ADR-0005](decisions/0005-semantic-type-classification.md).
2. **Measured join inference** — a relationship between two files is confirmed by real value
   overlap, not asserted by the model from column names alone.
   [ADR-0006](decisions/0006-join-inference.md).
3. **SQL guardrails + a self-repair loop** — validated before execution, one automatic retry
   with the exact failure fed back on error.
4. **Deterministic charts** — chosen from the real result, never guessed blind by the model.
   [ADR-0003](decisions/0003-rule-based-chart-selection.md).
5. **Full transparency** — every answer ships with its SQL, the tables it touched, whether it
   needed a repair, and any assumption the model made explicit (e.g. *"interpreting 'top' as
   highest performance_rating"*) rather than silently picking one.

## Tested scenarios (real runs, both sample datasets)

Two demo datasets ship with the repo — deliberately in different domains, so correctness isn't
an artifact of one convenient shape of data.

**HR dataset** (`sample-data/`) — employees, departments, a two-sheet salaries workbook:

| Question | Result |
|---|---|
| *Average base salary by department in 2024?* | Correct 3-table join, formatted ₹ figures, bar/pie chart |
| *How many employees were hired each year?* | Correct date grouping, line chart |
| *Who are the top 5 performers?* | Stated its own assumption (*"interpreting 'top' as highest performance_rating"*) rather than guessing silently |
| *Total revenue from customers in Antarctica?* | No matching rows — answered "0," did not hallucinate a number |
| *Average bonus in 2023 vs. 2024?* | Two-figure KPI comparison — a real bug found live (this was rendering as a one-point scatter plot before the fix in `charts.py`, see the progress log) |

**E-commerce dataset** (`sample-data/ecommerce/`) — customers, products, an orders fact table:

| Question | Result |
|---|---|
| *Total revenue from delivered orders?* | Correctly filtered to `Delivered` status only — KPI |
| *Total revenue by product category?* | 3-table join, pie chart |
| *How many orders were placed each month in 2024?* | Line chart, correct monthly grouping |
| *Which 5 customers spent the most?* | Correct join + aggregation, bar chart |
| *What percentage of orders were returned or cancelled?* | Correct filter + percentage calc, KPI |

All ten ran correctly on the first attempt — `repaired: false` on every one. Full detail on
every verification pass, including the bugs found and how they were fixed, in
[07 · Progress log](07-progress-log.md).

## Screenshots

*I don't have a browser tool in this session, so these five need to be captured by hand — save
each one to `docs/assets/` with the exact filename below and they'll render inline here and in
the GitHub README automatically. All five are ~30 seconds of work against the live app:*

1. `01-empty-state.png` — the live Vercel URL, before uploading anything
2. `02-schema-sidebar.png` — after uploading the HR sample files, showing the tables/join list
3. `03-answer-pie.png` — ask *"Total revenue by product category?"* on the e-commerce
   dataset — produces a pie chart
4. `04-sql-panel.png` — any answered question, with the "SQL used" section clicked open
5. `05-mobile-sheet.png` — resize the browser to ~400px wide (or your phone), tap "Data" in the
   header, screenshot the bottom sheet open

![Empty state — upload zone](assets/01-empty-state.png)
*First screen: no marketing hero, just what to do.*

![Schema sidebar after upload](assets/02-schema-sidebar.png)
*Tables, columns with semantic-type badges, and the inferred relationships between files.*

![A pie chart answer](assets/03-answer-pie.png)
*Answer → chart → table → collapsed SQL, in that order, every time.*

![The SQL transparency panel, expanded](assets/04-sql-panel.png)
*Every answer ships with the exact query that produced it.*

![Mobile — the data sheet](assets/05-mobile-sheet.png)
*Schema moves into a bottom sheet on small screens.*

## Known limitations (accepted, not hidden)

- **Single-instance only.** Sessions live in the backend's process memory — documented
  up front, not discovered later. [ADR-0004](decisions/0004-session-model.md).
- **Chart column semantics are coarser post-aggregation** than the ingestion profiler's —
  a `GROUP BY` on a numeric `identifier` column can't always be told apart from a genuine
  numeric measure once it's just a plain integer in the result set. Two concrete cases
  (year-named columns, single-row multi-metric comparisons) are handled explicitly; documented
  as an accepted limitation, not solved in general. See `charts.py`'s module docstring.
- **Column-name validation is intentionally shallow.** The SQL guard checks every table exists;
  it does not re-implement full SQL name resolution for columns — a wrong column name is
  caught by DuckDB's own precise error and handed to the repair loop instead, which is simpler
  and just as effective in practice.
- **Render's free tier sleeps** after ~15 minutes idle (~50s cold start) and has an ephemeral
  disk — both documented trade-offs of the free-tier choice, with a full alternative (Oracle
  Cloud free VM, no cold start) written up for when they matter.

## What's next

See [WRITEUP.md](../WRITEUP.md) for the four highest-value next steps, and
[08 · Roadmap](08-roadmap.md) for the complete list.

## Everything else

| Doc | Covers |
|---|---|
| [01 · Overview](01-overview.md) | Scope, acceptance criteria mapped to what was built |
| [02 · Architecture](02-architecture.md) | Full request-flow diagrams, module map |
| [03 · Data pipeline](03-data-pipeline.md) | Ingestion → naming → profiling → join inference, in depth |
| [04 · API reference](04-api-reference.md) | Every endpoint, request/response shapes |
| [05 · Local development](05-local-development.md) | Setup, running, testing, Windows-specific gotchas |
| [06 · Deployment](06-deployment.md) | Render + Vercel, step by step, plus the Oracle Cloud alternative |
| [07 · Progress log](07-progress-log.md) | Session-by-session build log — every bug found and fixed, with the reasoning |
| [08 · Roadmap](08-roadmap.md) | Milestone status, what's next, ordered by value |
| [09 · Frontend design direction](09-frontend-design-direction.md) | The design system, and why it deliberately avoids the generic "AI app" look |
| [decisions/](decisions/README.md) | Six ADRs — every major choice, the alternatives considered, the trade-off accepted |
