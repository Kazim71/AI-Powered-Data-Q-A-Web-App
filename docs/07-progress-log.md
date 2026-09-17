# 07 · Progress log

Append-only record of each working session: what was built, what broke, what was decided.
Useful raw material for the final write-up.

---

## 2026-09-17 · Session 1 — Scaffold + ingestion backend

### Built
- Repo structure: `backend/`, `frontend/` (placeholder), `docs/`, `sample-data/`
- **Session layer** — per-session DuckDB file + upload dir, thread-safe registry, TTL purge
- **Loader** — CSV via DuckDB `read_csv_auto`; Excel via pandas with one table per sheet;
  streamed uploads with early abort on size cap; partial success per file
- **Naming** — header normalisation with original labels preserved
- **Profiler** — dtype, semantic type, nulls, cardinality, top values, ranges, full category lists
- **Join inference** — name-based candidates scored by measured value overlap
- **Catalogue** — schema assembled once per upload batch and cached
- **API** — health, create/delete session, upload, schema, table preview
- **Sample data generator** — 3 related, deliberately messy files
- **Tests** — 26 passing (naming units + end-to-end ingestion)
- Dockerfile (non-root, honours `$PORT`), docker-compose, `.env.example`
- Full documentation set and six ADRs

### Verified manually (curl against a running server)
- 3 files → 4 tables, workbook split into `salaries_2023` / `salaries_2024`
- 4 correct join hints, all at 1.0 overlap
- Errors: unknown session 404, unknown table 404, `.pdf` rejected per-file while a CSV in the
  same batch succeeds, session delete 204 then 404
- Cached schema read: ~2.5 ms

### Bugs found and fixed during verification
These are the kind of thing an LLM-generated first draft gets subtly wrong, and why every
stage was run against real data rather than trusted.

| Bug | Symptom | Fix |
|---|---|---|
| 204 route with `-> None` annotation | Server crashed on boot: *"Status code 204 must not have a response body"* | Return an explicit `Response` with `response_class=Response` |
| Foreign key misclassified | `department_id` (5 distinct values in 120 rows) typed `categorical`, i.e. groupable like a label | Id-like names are always `identifier`, regardless of repetition |
| Rating demoted to category | `performance_rating` (4 values) typed `categorical`, so "average rating" would look wrong to the model | Low-cardinality numerics stay `numeric`, but still expose `categories` |
| Join noise | `salaries_2023.currency ↔ salaries_2024.currency` reported as a 100% join — both columns are constant `'INR'` | Reject degenerate keys: < 2 distinct, or non-identifier < 5 |
| Ugly table names | Sheet `2023` produced `salaries_c_2023` | Drop the digit guard when the slug is a suffix |
| Fragile provenance | Sheet name reverse-engineered by string-replacing the table name | Loader returns a `LoadedTable` dataclass carrying provenance |
| Wrong status code | Unknown table returned 400 | New `TableNotFound` → 404 |

### Environment notes
- pip broke on a stale `SSL_CERT_FILE` left by a PostgreSQL install → documented in
  [05 · Local development](05-local-development.md#known-environment-gotchas)

### Next
Milestone 2: `/ask` — prompt builder, LLM client (Groq + Ollama), sqlglot guard, repair loop,
chart picker.
