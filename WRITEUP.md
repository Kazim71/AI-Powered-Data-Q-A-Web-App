# Write-up

**Build an AI-Powered Data Q&A Web App — Forward Deployed Engineer take-home**

## Approach

The brief is really one question: *how do you get an LLM to answer analytical questions
correctly, on data it's never seen, without hallucinating numbers?* My answer was to never let
the model touch the data at all. Every uploaded file becomes a table in an embedded
[DuckDB](https://duckdb.org) database; the model's only job is to translate a plain-English
question into SQL against a **profile** of the schema (column types, value ranges, sample
values, inferred foreign keys) — never the rows themselves. DuckDB executes the query and
computes the actual answer. This means the numbers in the response are *computed*, not
*generated*, prompt size stays constant regardless of file size (so a free-tier open-weights
model is genuinely sufficient), and every answer ships with the exact SQL that produced it —
so a wrong answer is auditable, not a black box.

Multi-file, cross-file analysis (criterion #2) falls out of that architecture almost for free:
every uploaded file lands in one database, so a JOIN is just a JOIN. The harder problem was
making sure the *right* join happens without the model guessing — solved by measuring real
value overlap between candidate columns at upload time (not just matching names) and handing
the model verified relationships as facts, not asking it to infer them.

## Key decisions

- **NL → SQL over DuckDB**, not "paste the CSV into the prompt" or "let the model write and
  `exec()` pandas." See [ADR-0001](docs/decisions/0001-nl-to-sql-over-duckdb.md).
- **Column profiling before prompting.** Semantic typing (identifier vs. numeric vs.
  categorical) stops the model summing an ID column; complete value lists for low-cardinality
  columns stop it inventing `'Europe'` when the data says `'EMEA'`.
- **SQL safety by allow-list, not deny-list.** The guard asserts the parsed statement *is* a
  `SELECT`, rather than trying to enumerate every dangerous keyword — plus a function
  deny-list, since a plain `SELECT * FROM read_csv('/etc/passwd')` is syntactically an
  innocent SELECT. One self-repair round-trip on failure, feeding the exact DB error back to
  the model.
- **Charts are chosen by rules over the *executed result's* shape, never by the LLM** — the
  model writes SQL before it has seen the result, so letting it also pick the chart type means
  guessing blind. Deterministic and unit-testable with zero network calls.
- **Open-weights via Groq, Ollama as a drop-in local fallback**, behind one interface — meets
  the brief's constraint and gives a real "runs fully on-prem" story for an HR-adjacent
  product where data residency matters.

## What I'd build next

1. **Conversation memory** — resolve a follow-up ("now just EMEA") against the previous
   question's SQL instead of starting cold each time.
2. **A semantic layer** — user-defined metrics (`attrition_rate = ...`) so business vocabulary
   maps to deterministic SQL instead of a fresh LLM interpretation on every question.
3. **Confidence signalling** — generate SQL twice at different temperatures and flag
   disagreement, instead of always asserting a single number with full confidence.
4. **A shared session store** (Redis) — the current in-process session registry caps the app
   at one instance; fine for a prototype, the real blocker before it could take real traffic.

Full reasoning, alternatives considered, and every bug found during verification are in
[docs/](docs/README.md) — start at [docs/07 · Progress log](docs/07-progress-log.md) for the
warts-and-all version, or [docs/10 · Project overview](docs/10-project-overview.md) for the
fuller narrative.
