# 08 · Roadmap

## Milestones

### ✅ M1 — Ingestion backend
Upload, normalise, profile, infer joins, cache schema. 26 tests.

### ✅ M2 — Question answering (`/ask`)
- [x] `query/prompts.py` — render `SessionSchema` (+ join hints) into a compact prompt;
      strict-JSON contract for SQL generation, repair, and answer summary
- [x] `query/llm.py` — provider interface; Groq and Ollama implementations, chosen by
      `LLM_PROVIDER`; defensive JSON extraction for both
- [x] `query/sql_guard.py` — sqlglot parse; allow-list on statement shape (SELECT/WITH/set-ops
      only, not a keyword deny-list); function deny-list (`read_csv`, `getenv`, ...); table
      existence; row cap injected as `cap + 1` for truncation detection
- [x] `query/executor.py` — async execution with a real timeout (`interrupt()` from the event
      loop thread) and row-cap enforcement
- [x] Repair loop: one retry feeding the exact failure back to the model — covers both a
      sqlglot rejection and a DuckDB execution error
- [x] `query/charts.py` — pure, deterministic result shape → chart spec (KPI/line/bar/pie/
      scatter/table)
- [x] One-sentence natural-language answer from the result; falls back to a plain
      "Returned N rows..." if that call fails, so a flaky summary never discards a
      successful query
- [x] 48 new tests: `sql_guard` (allow-list, function deny-list, row cap), `charts` (every
      rule branch), JSON extraction, and full `/ask` orchestration against a scripted fake
      LLM client — including the repair loop and a rejected `DROP TABLE` — **74 total,
      no network calls in CI**
- [x] *Manual verification against a real model* (session 3, once a Groq key was available):
      four real questions — cross-file join+aggregation, a date-trend query, a deliberately
      ambiguous "top performers" question, and a zero-result question — all correct on the
      first attempt. Found and fixed two real issues in the process: the planned
      `llama-3.3-70b-versatile` model had been deprecated by Groq (switched default to
      `openai/gpt-oss-120b`), and a year-grouped result was charted as a scatter plot (fixed
      in `charts.py`, now a `line`). Still not an *automated* test — a real model call stays
      too slow/costly/non-deterministic for CI — but the "does it actually work" question is
      answered. See the session 3 entry in [07 · Progress log](07-progress-log.md).

### ✅ M3 — Frontend
- [x] Next.js 16 (App Router) + TypeScript + Tailwind v4 scaffold
- [x] Design system defined *before* implementation, in
      [09 · Frontend design direction](09-frontend-design-direction.md) — colour, type
      (Public Sans + IBM Plex Mono, not Inter/Geist/Space Grotesk), spacing, restrained radius,
      motion, information architecture — per that doc's own process requirement
- [x] Hand-rolled UI primitives (Button, Badge, StatusBanner) restyled directly from the
      tokens, in place of the shadcn CLI — see the progress log for why
- [x] Drag-and-drop + click-to-browse multi-file upload with per-file status
      (`UploadZone.tsx`, `UploadProgressList.tsx`); progress is one aggregate bar (honest to
      what the browser's upload-progress event actually gives us for a multi-file POST), with
      each file's individual ok/failed outcome shown once the server responds
- [x] Schema sidebar (desktop) / bottom sheet (mobile), sharing one `SchemaContent` component:
      tables, columns with semantic-type badges, inferred join hints
- [x] Ask bar → turn history: answer → assumptions → chart → table → SQL (collapsed), per the
      brief's progressive-disclosure order, every turn, regardless of outcome
- [x] `ChartView.tsx` renders exactly the `chart.type` the backend's rule engine chose — no
      chart-selection logic on the frontend at all
- [x] States covered: empty, uploading, partial upload failure, no files yet, asking (pending
      turn), answer, SQL repaired (shown, not hidden), truncated result, no rows, session
      expired (404 → reset flow), backend cold start (>4s → "waking up" notice, request still
      in flight)
- [x] Responsive: sidebar → bottom sheet at `md`, 44px+ touch targets, table scrolls in its
      own container
- [x] `next build` succeeds, `tsc --noEmit` and `eslint` both clean
- [x] Verified via SSR HTML output and compiled CSS against a running backend (no browser tool
      available this session — see the session 4 entry in the progress log for exactly what
      was and wasn't checked, and what still needs a real click-through before the demo)
- [ ] Chat pane → answer, chart (Recharts), result table, collapsible SQL panel
- [ ] Suggested starter questions derived from the schema

### ⏳ M4 — Ship
- [ ] Deploy backend (Render) and frontend (Vercel)
- [ ] README with architecture diagram and demo GIF
- [ ] 1-page write-up
- [ ] Demo recording

---

## Beyond the assignment — what I'd build next

Ordered by value to a real customer, not by effort.

1. **Conversation memory.** Follow-ups like "now only for Mumbai" resolved against the
   previous question's SQL.
2. **Semantic layer.** User-defined metrics (`attrition_rate = …`) so business vocabulary
   maps to deterministic SQL instead of an LLM interpretation each time.
3. **Confidence signalling.** Generate SQL twice at different temperatures; if results
   disagree, say so rather than asserting a possibly wrong number.
4. **Tenant isolation and row-level security.** The real blocker for HR data.
5. **Shared session store.** Move the in-process registry to Redis + object storage so the
   backend can scale horizontally.
6. **Fine-tuned small local SQL model** for customers who cannot send even schema metadata to
   an external API.
7. **Saved questions → dashboard.**
