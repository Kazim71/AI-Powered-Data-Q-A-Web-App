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

---

## 2026-09-17 · Session 2 — Question answering (`/ask`)

### Built
- **`query/prompts.py`** — schema (+ measured join hints) rendered into a compact prompt;
  strict-JSON contract for three calls: SQL generation, SQL repair, answer summary
- **`query/llm.py`** — `LLMClient` protocol; `GroqClient` (OpenAI-compatible endpoint) and
  `OllamaClient` (native `/api/chat`, `format: "json"`), chosen by `LLM_PROVIDER`; defensive
  `_extract_json` recovers from markdown fences and stray preamble text
- **`query/sql_guard.py`** — allow-list on statement shape (root must be `SELECT`/`WITH`/a
  set-op over selects — not a keyword deny-list, so nothing needs enumerating to reject it),
  plus a function deny-list (`read_csv`, `read_parquet`, `getenv`, `current_setting`, ...) as
  defense in depth against a SELECT that reads outside the uploaded tables. Table existence
  checked strictly; column existence deliberately left to execution + the repair loop rather
  than reimplementing SQL name resolution. Row cap injected as `cap + 1` so truncation is
  detectable without a second query
- **`query/executor.py`** — async execution; DuckDB has no query-timeout argument, so the
  query runs on a worker thread and `connection.interrupt()` is called from the event loop on
  timeout (DuckDB's documented cross-thread cancellation pattern)
- **`query/charts.py`** — pure function, result shape → `ChartSpec`. Column "kind" inferred
  from the Python types DuckDB returns, since a query result carries no semantic-type metadata
  from the source schema post-aggregation (documented limitation: a `GROUP BY` on a numeric
  `identifier` can't be told apart from a genuine numeric measure — see the module docstring)
- **`query/service.py`** — orchestrates generate → validate → execute → repair-once → chart →
  summarise; a failed summary call falls back to a plain description rather than discarding an
  otherwise-successful query
- **`POST /api/sessions/{id}/ask`** wired in `api/routes.py`
- **48 new tests** (74 total): `test_sql_guard.py` (allow-list, function deny-list, CTE alias
  handling, row-cap injection/tightening), `test_charts.py` (every rule branch in the ADR-0003
  table), `test_llm_json_extraction.py`, `test_ask_api.py` (full `/ask` pipeline against a
  scripted `FakeLLMClient` — happy path, repair loop, repair-also-fails, a rejected
  `DROP TABLE` treated as an ordinary failed attempt, empty-session 400, summary-call fallback,
  request validation)
- Refactored upload-related test helpers into `conftest.py` (`upload_files`,
  `upload_sample_files`, `populated_session_id` fixture) so `test_ask_api.py` doesn't
  duplicate `test_ingestion_api.py`'s multipart-upload plumbing
- Docs updated throughout: architecture's ask flow, full `/ask` API reference, overview's
  acceptance-criteria table (all four now ✅), roadmap

### Verified manually (curl against a running server, no LLM key configured)
- `POST /ask` on an empty session → `400 {"error": "Upload at least one file..."}`, confirming
  the guard runs *before* any LLM call
- `POST /ask` with data uploaded but no `GROQ_API_KEY` → `502` with a message that tells the
  user exactly what to do (set the key, or switch to `LLM_PROVIDER=ollama`), not a stack trace
- Empty-string question → `422` from Pydantic validation, before the request reaches the
  service layer at all

### Design decisions made while building (not pre-planned)
- **Allow-list beats deny-list for statement shape.** The original plan was "block DDL/DML by
  keyword"; implementing it made clear that's an open-ended list (PRAGMA, ATTACH, COPY, SET,
  MERGE, ...). Asserting the root node's *type* is one of `{Select, Union, Intersect, Except}`
  rejects everything else by construction — including sqlglot dialect quirks that would need
  discovering one at a time under a deny-list.
- **A SELECT can still escape the sandbox via table functions.** `SELECT * FROM
  read_csv('/etc/passwd')` is a syntactically ordinary SELECT. Added the function deny-list
  specifically because the allow-list alone doesn't stop it.
- **Column validation intentionally scoped down.** Full column-name resolution against aliases
  and expressions is real SQL semantic analysis. Decided that table-existence checking (guard)
  plus DuckDB's own precise "column not found" error (caught and handed to the repair prompt)
  gives equivalent safety with far less code — the repair loop is the actual column-validator.
- **Row-cap-plus-one trick for truncation.** Rather than issuing a second `COUNT(*)` query to
  detect truncation, requesting `cap + 1` rows and checking whether the extra one came back is
  one query instead of two, at negligible cost.
- **A fake LLM client, not a live one, for the test suite.** A real Groq/Ollama call in tests
  would make CI depend on network access, an API key, and non-deterministic model output —
  the exact opposite of what the SQL-guard and chart-picker unit tests are for. `FakeLLMClient`
  scripts exact JSON responses per call, which also makes the repair loop and the
  rejected-DROP path fully deterministic to test. A real-model smoke test remains valuable
  before the demo recording but doesn't belong in the automated suite (see roadmap M2).

### Next
Milestone 3: frontend. Read [09 · Frontend design direction](09-frontend-design-direction.md)
first — it's a binding brief, not a suggestion.

---

## 2026-09-17 · Session 3 — Live Groq verification + hosting decision

### Verified against the real model (not the fake client)
First real end-to-end run with a live Groq key. Three questions against the sample data, all
correct on the first attempt (`repaired: false`):

- *"Average base salary by department in 2024?"* → correct 3-table join
  (`salaries_2024 ⋈ employees ⋈ departments`), formatted answer with real ₹ figures
- *"How many people were hired each year?"* → correct `EXTRACT(YEAR FROM hire_date)` grouping
- *"Who are the top 5 performers?"* → correctly stated its own assumption
  (*"interpreting 'top' as highest performance_rating"*) rather than guessing silently
- *"Total revenue from customers in Antarctica?"* → no matching rows, answered "0" instead of
  hallucinating a number, and surfaced the assumption that revenue = base salary + bonus

### Bug found and fixed
| Bug | Symptom | Fix |
|---|---|---|
| Year-grouped result charted as scatter | `SELECT EXTRACT(YEAR ...) AS hire_year, COUNT(*)` returns two plain integers post-aggregation — nothing distinguishes "time axis" from "second measure" | `charts.py`: a numeric column named `year`/`month`/`quarter`/`week`/`period` is reclassified as the time axis when another numeric measure remains, so it charts as a `line` |

Also: `GROQ_MODEL=llama-3.3-70b-versatile` (the model named in the original plan) has been
deprecated by Groq and returns `404 model_not_found`. Switched the default to
`openai/gpt-oss-120b` — OpenAI's Apache-2.0 open-weight release, hosted on Groq. Still meets
the brief's open-source requirement, and performed well on all four test questions above.

### Hosting decision
Clarified for the user: there is no separate database to host. DuckDB is embedded in the
backend process — a session's "database" is a `.duckdb` file on the same disk as the API. The
real decision is only where the **backend process** runs. See
[06 · Deployment](06-deployment.md#backend-hosting-render-vs-oracle-cloud-free-vm) for the
Render-vs-Oracle-VM comparison and the Oracle setup guide added there.

User decided: Render for now (deadline), with the explicit caveat that Render alone won't fix
"can't handle traffic if I add a chatbot" — flagged in reply that the app's own architecture
(in-process session registry, [ADR-0004](decisions/0004-session-model.md)) caps it at one
instance regardless of host, which is the thing to fix first if scaling ever matters, not the
choice of platform.

---

## 2026-09-18 · Session 4 — Frontend (M3)

### Design system, written before any component code
Per the binding brief's own process requirement, [09 · Frontend design
direction](09-frontend-design-direction.md) was extended with the concrete system before
writing a single component: information architecture (one route, no "results page" — each
question appends a turn to a running log), layout (two-pane desktop, sheet on mobile), full
colour tokens (light + dark), a two-typeface system (Public Sans for UI, IBM Plex Mono for
every number/SQL/column name — deliberately not Inter/Geist/Space Grotesk), spacing/radius/
motion rules.

### Built
- **Scaffold**: Next.js 16 (App Router, Turbopack) + TypeScript + Tailwind v4 + React 19.
  Tailwind v4's `@theme inline` maps the CSS custom properties in `globals.css` straight into
  utility classes (`bg-primary`, `text-error`, ...), so the token doc and the code can't drift.
- **Fonts** via `next/font/google` (self-hosted at build time, confirmed via SSR HTML: the
  `Public_Sans`/`IBM_Plex_Mono` variable classes are present, no runtime Google Fonts request).
- **`lib/types.ts`** — hand-written TS twin of `backend/app/models.py`.
- **`lib/api.ts`** — typed client for all four endpoints. Upload goes through `XMLHttpRequest`
  specifically for `upload.onprogress` (fetch's request-body progress isn't reliably
  observable yet); `ask()` takes an `onSlow` callback that fires after 4s without cancelling
  the request, to drive a "waking up" cold-start notice instead of a silent wait.
- **`hooks/useWorkspace.ts`** — the one hook holding all app state (session, schema, uploads,
  turns) and every API call; `page.tsx` and every component below it are pure rendering.
- **Components**: `EmptyState`, `UploadZone` (drag-and-drop, keyboard-operable),
  `UploadProgressList`, `SchemaSidebar`/`DataSheet`/`SchemaContent` (desktop sidebar and
  mobile bottom sheet share one content component so they can't drift), `AskBar`, `Turn`
  (answer → assumptions → chart → table → SQL, the brief's progressive-disclosure order,
  every time regardless of outcome), `ChartView` (renders whichever `chart.type` the backend
  chose — no chart-selection logic on the frontend), `ResultTable` (scrolls in its own
  container, tabular-numeric right-aligned cells).
- Hand-rolled `ui/Button`, `ui/Badge` (including the semantic-type dot+label used in the
  schema sidebar), `ui/StatusBanner` — restyled directly from tokens rather than via the
  shadcn CLI (see "Design decisions" below).
- States implemented: empty, per-file uploading/ok/failed, no files yet, question pending,
  answer, assumptions (accent badges — not styled as errors), repaired query (warning banner),
  truncated result (info banner), no rows, session expired (backend 404 → reset flow), cold
  start (info banner, request still in flight).

### Verified
- `tsc --noEmit`, `eslint`, and `next build` all clean (two real type errors surfaced and
  fixed along the way — Recharts' `PieLabelRenderProps` isn't indexable by a plain string key,
  needed an explicit cast).
- Ran the actual production build (`next start`) against the real backend on
  `localhost:8000`, hit it with curl: the empty-state SSR HTML matches the design exactly
  (heading, copy, upload zone — no marketing hero), and the compiled CSS confirms the token
  pipeline works end to end (`.text-error{color:var(--error)}`,
  `bg-primary\/5{background-color:color-mix(in oklab, var(--primary) 5%, transparent)}`).
- **Not verified this session:** an actual click-through in a browser — no browser tool was
  available. Upload → ask → chart render → mobile sheet → keyboard navigation all still need a
  real pass before the demo recording. This is a real gap, not a formality — flag it in any
  later session before calling M3 done.

### Environment gotcha found
`npx <anything>` fails with `Cannot find module '...'` on this machine — root cause: the repo
path contains `Q&A`, and something in npx's Windows child-process spawning mishandles the
literal `&` (same *category* of Windows-path issue as the earlier `SSL_CERT_FILE` one, different
mechanism). Workaround, documented in `frontend/README.md`: call the local binary directly,
e.g. `node node_modules/next/dist/bin/next build` instead of `npx next build`.

### Design decisions made while building
- **Hand-rolled UI primitives instead of the shadcn CLI.** The brief allows either
  ("primitives only, restyled ... so it never reads as the shadcn demo"). For three small
  components (Button, Badge, StatusBanner) at this scope, hand-rolling directly against the
  token system was faster and left zero default-shadcn styling to override — same end state,
  less risk, no interactive CLI prompts to script around.
- **Watermelon UI and Motion Primitives evaluated, not installed.** Nothing in the workspace
  UI (upload, ask, turn history, schema browser) needed a component distinctive enough to
  justify a registry pull over a native element — the schema sidebar's disclosure uses native
  `<details>`/`<summary>` (keyboard-operable and semantic for free) instead of a custom
  accordion. Motion is a handful of CSS transitions/keyframes.
- **Upload progress is one aggregate bar, not true per-file bars.** A single multipart POST
  gives one `progress` event for the whole request body — browsers don't expose per-file
  upload progress within one request. Faking individual bars would be dishonest about what's
  actually known; each file's real, individual outcome (ok/failed/tables created) is shown
  once the server responds, which is the information that actually matters.
- **Session-expired detection uses the existing 404, not a 410.** The original design-doc
  draft speculated "410 Gone" for an expired session; the backend actually returns 404
  (`SessionNotFound`, built in M1) for the same case, and there was no reason to add a second
  status code for one already-handled condition — `useWorkspace` treats any 404 from `ask()`
  as expiry and shows the reset flow.

### Next
A real browser pass (upload → ask → every chart type → mobile sheet → keyboard-only
navigation) before this milestone is actually done, then M4: deploy to Render + Vercel, README
polish, the 1-page write-up, demo recording.

---

## 2026-09-19 · Session 5 — Live troubleshooting: session-expired mislabelling, `npm run dev`

User reported the frontend showing "This session has expired" immediately on first upload.

### Root cause
The backend simply wasn't running — the frontend was up, but there was nothing at
`localhost:8000`. That's an easy mistake to make and not itself a bug.

### Real bug found and fixed
`useWorkspace.ts`'s `handleFilesSelected` caught *any* failure from `createSession()` — network
refused, CORS, wrong URL, or an actual expired session — and mapped all of them to the same
"session expired, start a new session" screen. That's actively wrong for the common case: a
`createSession()` call has no existing session to have expired, so *every* failure there is a
connectivity/config problem, and "start a new session" would fail identically. Fixed by:
- `lib/api.ts`: `fetch` throwing a bare `TypeError` (refused connection, DNS failure, CORS
  rejection) is now normalised into the same `ApiError` shape as an HTTP error response
  (`status: 0`, matching the convention `uploadFiles`'s XHR path already used), with a message
  that actually says what's wrong and where it tried to connect.
- `useWorkspace.ts`: added a distinct `connectionError` state, shown inline in `EmptyState`
  rather than taking over the whole screen. `sessionExpired` now only fires on a genuine 404
  from a session that existed and is now gone — checked separately in the upload-batch catch
  too, which previously only had the generic "mark files failed" path.

### Also, while in there: real UX gaps
- No way to start a fresh session once one existed, other than triggering the error screen —
  added a persistent "New session" action in the header.
- No indication of upload limits (file types, 50 MB, 10 files) before hitting them — added a
  caption under the upload zone.
- Multiple turns had no visual separation in the running log — added a rule between them.

### Second issue: `npm run dev` itself was broken, not just `npx`
Same root cause as the earlier `npx` gotcha (this checkout's path contains "Q&A", and `cmd.exe`
— npm's default Windows script shell — treats the literal `&` as a command separator) but wider
than previously scoped: it broke **every** npm script (`dev`, `build`, `lint`, `start`), not
just one-off `npx` calls. Fixed with `frontend/.npmrc` setting `script-shell` to Git Bash, which
handles the `&` correctly. Verified `dev`/`build`/`lint` all work with it in place.

### Next
Deploy prep (M4) surfaced two more real issues around this exact file — see the session 6 entry.

---

## 2026-09-20 · Session 6 — Vercel deployment prep

Asked to prepare the frontend for Vercel. Checked what was actually committed before touching
anything, since the user commits their own work now — found two real problems in what had
already landed.

### Bug found and fixed: `frontend/.npmrc` was committed
The `.npmrc` fix from session 5 (`script-shell` pointed at Git Bash to work around the `&`-in-
path bug) got committed. That file hardcodes a **Windows** path
(`C:\Program Files\Git\bin\bash.exe`). Vercel builds on Linux — that path doesn't exist there,
so a deploy would have failed on the very first `npm install`/`npm run build`, for a reason
that would have looked completely unrelated to anyone reading the error.

Fixed: `git rm --cached` (kept the file on disk — still needed locally), added `.npmrc` to
`frontend/.gitignore` with an explanatory comment, documented in `frontend/README.md` as a
machine-local file to recreate if the same bug shows up elsewhere, not a project setting.
Confirmed by literally removing it and running `npm run build` on this machine: reproduces the
exact original failure — proving the fix is real and, just as importantly, that Vercel's Linux
build environment was never at risk from this bug in the first place (no `cmd.exe`, and their
build path won't contain `&`).

### Bug found and fixed: `frontend/.env.example` was never actually committed
`create-next-app`'s default `frontend/.gitignore` has a blanket `.env*` rule, written before
this project decided to commit an example env file. It silently swallowed
`frontend/.env.example` — `git status` showed nothing wrong because the file was never staged
in the first place, not because it was later removed. Anyone cloning the repo fresh had no
record of `NEXT_PUBLIC_API_URL`, the one env var the frontend needs. Fixed with a `!.env.example`
negation line and committed the file.

### Documentation
Expanded [06 · Deployment](06-deployment.md) with a concrete step-by-step Vercel section (Root
Directory is the setting most likely to be missed in a monorepo import — the repo root has no
Next.js app in it, so an unset Root Directory fails the build immediately) and a new
**Deployment order** section up front, since Render and Vercel need each other's URL — backend
first (CORS placeholder is fine initially) → frontend, with `NEXT_PUBLIC_API_URL` set correctly
*before* the first build since it's inlined at build time, not read at runtime → back to Render
to set the real `CORS_ORIGINS` once the Vercel URL is known.

### Verified
`tsc --noEmit`, `eslint`, and `next build` all still clean after the `.gitignore`/tracking
changes (which don't touch app code, but worth confirming nothing else regressed).

### Not done this session
Nothing was actually deployed — that needs the user's own Vercel/Render accounts, which I don't
have access to. Everything above is prep; the deploy itself is still the next step.

---

## 2026-09-20/21 · Session 7 — First real deploy, live debugging, submission prep

The actual first deployment, done together with the user live: I diagnosed each failure from
screenshots/pasted logs (no browser tool this session), the user made the dashboard changes.

### Deploy issues hit, in order, each a real config problem, not a code bug
1. **Render: `Dockerfile: no such file or directory`.** Root Directory wasn't set to
   `backend`, so Render looked for the Dockerfile at the repo root. Fixed in Render Settings.
2. **Vercel: platform-level 404 on every route**, despite the build reporting "Ready." Root
   Directory *was* correctly set to `frontend` this time — the actual cause was **Framework
   Preset** not being "Next.js." When Vercel doesn't know it's building a Next.js app, it
   serves the build output as plain static files instead of through the Next.js runtime, so
   the build succeeds but nothing is servable. This is a materially different failure mode
   from #1 and worth knowing apart: "build succeeded but every route 404s" almost always means
   framework detection, not a missing file.
3. **`NEXT_PUBLIC_API_URL` not set** → app correctly showed "Could not reach the server at
   `http://localhost:8000/api`" (the connection-error fix from session 5, working exactly as
   designed, live, for the first time). Vercel additionally blocked saving the variable at all
   under its newer **Secret vs. Config** type distinction: a `NEXT_PUBLIC_` key can't be typed
   "Secret" (write-only, never re-readable) because it's inlined into the public JS bundle by
   definition — Vercel now requires "Config" (readable, non-sensitive) for any
   `NEXT_PUBLIC_`-prefixed key. Not documented anywhere I'd already written; worth knowing for
   next time.
4. **CORS**: `CORS_ORIGINS` on Render was still the local placeholder
   (`http://localhost:3000`) from before Vercel existed. Confirmed via a raw OPTIONS preflight
   with `curl` before touching the dashboard (no `access-control-allow-origin` header came
   back for the Vercel origin) and again after the fix (header present) — cheaper and more
   certain than trial-and-error in the browser.
5. **Two local commits were never pushed to GitHub** (`16de2aa` M2, `e84018c` env fix) — Render
   had only ever built the very first commit. Caught by comparing `git log` against
   `git log origin/master --oneline`, not by guessing.

Backend fully verified end-to-end through the real public URLs (session created, files
uploaded, a real question answered correctly) after each fix, via `curl` with an explicit
`Origin` header matching what a real browser sends — not just "the button worked," but
confirmation the exact mechanism (CORS, env inlining) was actually fixed.

### Real bug found from a live screenshot: single-row multi-metric comparison charted as scatter
*"What's the average bonus in 2023 compared to 2024?"* returned two numeric columns
(`avg_bonus_2023`, `avg_bonus_2024`) in one row. The old KPI rule only matched exactly one
numeric column, so this fell through to "two numerics → scatter," rendering as a scatter plot
of a single point — meaningless, and visibly wrong in the screenshot the user sent. Fixed:
`charts.py`'s KPI rule now matches *any* single-row, numbers-only result, not just one column;
`ChartView.tsx`'s KPI branch now renders a grid of stat tiles when there's more than one
value, not just the first one. Two new tests pin the exact scenario from the screenshot.
Verified locally (this fix isn't live yet — needs a push + redeploy).

Also improved while fixing this: the pie chart's inline labels (full names/categories printed
directly on the slice) were colliding and overlapping once there were more than 3–4 slices,
visible in the same screenshot — switched to percentage-only inline labels plus a proper
`<Legend>` below mapping colour to name. Added a `<Legend>` to multi-series bar/line charts
too, which previously had no way to tell which colour meant which series.

### Added: a second sample dataset
`sample-data/ecommerce/` — customers/products/orders, deliberately a different domain from the
HR dataset, so "it works" isn't an artifact of one convenient shape of data. Ran 5 real
questions against it locally (KPI, pie, line, bar, another KPI) — all correct first try, zero
repairs. Both datasets' verified results are now in `docs/10-project-overview.md`.

### Documentation
- **`WRITEUP.md`** (repo root) — the ≤1-page write-up the brief explicitly requires
  (approach, key decisions, what's next). Existed nowhere until this session.
- **`docs/10-project-overview.md`** — a new, self-contained what/why/how doc for
  presentation/review: the core idea, full request-flow walkthrough, a stack-choice table with
  rejected alternatives named for each row, the tested-scenarios table from both datasets, and
  known limitations stated up front rather than left for a reviewer to find.
- Screenshots: **not captured this session — no browser tool available.** Wired five
  placeholders into `docs/10-project-overview.md` pointing at exact filenames in `docs/assets/`
  with a precise, ~2-minute capture list (what to screenshot, in what state), so dropping the
  files in is the only remaining step.

### Not done this session
The chart fix and second sample dataset are not live — need a commit, push, and redeploy on
both Render and Vercel (should be quick now that the deploy pipeline itself is proven to work).
Screenshots need the user to capture them by hand, per the list above. The theme/UI was
reported as "very bad" by the user with no specifics given and no browser access on my end to
diagnose further — made the concrete, justifiable fixes above (pie legibility, KPI layout) but
did not attempt to guess-and-redesign the rest blind; asked the user for specifics in chat.
