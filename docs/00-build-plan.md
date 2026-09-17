# AI-Powered Data Q&A Web App — Build Plan

Darwinbox FDE take-home. Budget: 4–6 focused hours. Everything free-tier.

---

## 1. Scoping decision (the thing they're actually grading)

The brief says you're judged on **scoping under ambiguity** and **delta solutioning on top of what AI does**
— not on code. So the plan is built around one core architectural choice and three "delta" features.

**Core choice: NL → SQL over DuckDB. Not "LLM reads the dataframe".**

Three candidate approaches:

| Approach | Verdict |
|---|---|
| Stuff CSV rows into the prompt, let the LLM answer | ❌ Breaks past ~100 rows, hallucinates numbers, no cross-file joins |
| LLM writes Python/pandas, we `exec()` it | ⚠️ Works, but arbitrary code execution + fragile across dtypes |
| **LLM writes SQL, DuckDB executes it** | ✅ **Chosen** |

Why DuckDB wins here:
- Reads CSV **and** Excel natively, in-process, zero server. `SELECT * FROM 'file.csv'`.
- Multi-file → multi-table → **cross-file JOINs are free**. That's acceptance criterion #2, solved by the storage engine rather than by prompt engineering.
- The LLM never sees the data, only the **schema**. Constant-size prompt regardless of file size → tiny, cheap, works on a small open-source model.
- SQL is auditable. You can show the user exactly how the number was computed. That is the single strongest anti-hallucination story you can tell the panel.

**The "delta solutioning" (criterion #4) — what you add on top of raw LLM output:**
1. **Guardrail + repair loop.** Validate generated SQL (read-only, table/column names must exist). On execution error, feed the error back once for self-repair. Never `exec` arbitrary code.
2. **Semantic profiling layer.** Before asking the LLM anything, profile every column: dtype, null %, cardinality, min/max, top-5 sample values. Feed *that* into the prompt, not just column names. This is what makes it answer `"revenue by region"` correctly when the column is literally named `rgn_cd`.
3. **Auto-join inference.** Detect shared keys across uploaded files (name similarity + value-overlap sampling) and state them explicitly in the prompt as join hints.
4. **Deterministic chart selection.** The LLM does *not* draw the chart. A rule engine inspects the *result set shape* (1 row × 1 col → KPI card; categorical + numeric → bar; date + numeric → line; 2 numerics → scatter) and picks. Charts can't hallucinate.
5. **Transparency panel.** Every answer ships with the SQL, row count, and the tables touched. Collapsible.

---

## 2. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser — Next.js / React + Tailwind + shadcn + Recharts   │
│  Upload zone · Chat pane · Result table · Chart · SQL panel │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST (JSON + multipart)
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI (Python)                                            │
│                                                              │
│  POST /session            → new session id                   │
│  POST /upload             → ingest + profile                 │
│  GET  /schema             → tables, columns, join hints      │
│  POST /ask                → NL question → answer             │
│                                                              │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│  │ Ingestion  │→ │  Profiler    │→ │ Schema Context    │    │
│  │ pandas/    │  │  dtypes,     │  │ Builder (compact  │    │
│  │ openpyxl   │  │  nulls,      │  │ text card/table)  │    │
│  └────────────┘  │  samples     │  └─────────┬─────────┘    │
│        │         └──────────────┘            │              │
│        ▼                                     ▼              │
│  ┌──────────────┐                  ┌──────────────────┐     │
│  │   DuckDB     │◀── validated ────│  LLM: NL → SQL   │     │
│  │  (1 file per │     SQL          │  (open-source)   │     │
│  │   session)   │──── error ──────▶│  + repair loop   │     │
│  └──────┬───────┘                  └──────────────────┘     │
│         │ result DataFrame                                   │
│         ▼                                                    │
│  ┌──────────────┐   ┌────────────────────┐                  │
│  │ Chart picker │   │ LLM: result → 1–2  │                  │
│  │ (rule-based) │   │ line NL summary    │                  │
│  └──────────────┘   └────────────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

**Request flow for `/ask`:**
1. Load session schema context (cached).
2. Prompt LLM: schema + join hints + question + few-shot SQL examples → SQL only.
3. Validate: parse with `sqlglot`; reject anything that isn't a single `SELECT`/`WITH`; assert every referenced table exists.
4. Execute in DuckDB with a `LIMIT` cap and a statement timeout.
5. On error → one repair round-trip with the error text. Then fail gracefully with the SQL shown.
6. Rule-engine picks chart spec from result shape.
7. Second cheap LLM call turns the (small) result into a one-line natural answer.
8. Return `{ answer, sql, columns, rows, chart_spec, tables_used }`.

---

## 3. Tech stack

| Layer | Pick | Why |
|---|---|---|
| Frontend | **Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui** | Fastest path to a UI that looks finished; deploys free on Vercel |
| Charts | **Recharts** | Declarative, tiny, pairs perfectly with a JSON chart spec |
| Backend | **FastAPI + Python 3.11** | Pandas/DuckDB ecosystem lives here; async; auto OpenAPI docs |
| Analytics engine | **DuckDB** (`duckdb` py pkg) | The core decision above |
| File parsing | **pandas + openpyxl** (`read_excel`, all sheets) | Handles .xlsx/.xls; each sheet becomes its own table |
| SQL validation | **sqlglot** | AST-level parsing, dialect-aware, catches non-SELECT |
| LLM | **Groq API — `llama-3.3-70b-versatile`** (open-weights model, free tier, very fast) | Brief says *open-source models*. Llama 3.3 is open-weights. Groq gives a generous free tier and sub-second latency. |
| LLM fallback | **Ollama + `qwen2.5-coder:7b`** locally | Proves it runs fully offline/on-prem — a strong FDE talking point for an HR-SaaS company with data-residency concerns |
| LLM plumbing | Plain `httpx` calls, or LiteLLM if you want provider-swap in one line | Avoid LangChain — it's a lot of abstraction for two prompts |
| Session store | DuckDB file on disk + in-memory dict, keyed by session UUID | No DB needed for a prototype |

**Deliberately NOT using:** LangChain agents, a vector DB, RAG, Postgres, auth, Redis. None of them earn their complexity in 6 hours, and each is a thing that can break during the demo.

---

## 4. Deployment (free tier)

**Recommended: split deploy.**

| Piece | Platform | Notes |
|---|---|---|
| Frontend | **Vercel** free | Native Next.js, instant, custom domain |
| Backend | **Render** free web service (Docker) | Simplest Python+Docker free tier. Caveat: **spins down after 15 min idle → ~50s cold start.** Hit it once before the demo. |

**Alternatives, ranked:**
- **Railway** — $5/mo trial credit, no cold starts, nicer DX. Best experience if you accept the credit limit.
- **Hugging Face Spaces (Docker)** — free, no sleep, and thematically on-brand for an "open-source AI models" brief. Strong dark-horse pick; can host the whole thing single-container.
- **Oracle Cloud Free Tier (ARM Ampere VM)** — genuinely always-free and powerful (up to 4 OCPU / 24 GB RAM, enough to run Ollama for real). But you pay in setup time: VM, nginx, TLS, systemd. **Only pick this if you want to demo the fully-local Ollama path.** Otherwise it's an hour you don't have.

**Decision: Vercel + Render for the hosted link.** Keep a `docker-compose up` path in the README as the reliable local fallback, and record the demo video against local so no cold start ever ruins it.

⚠️ Important on Render free: uploaded files and the DuckDB file live on **ephemeral disk** — they vanish on restart. That's fine (sessions are meant to be ephemeral) but say so in the README so it reads as a decision, not a bug.

---

## 5. Repo layout

```
ai-data-qa/
├─ README.md                 # setup, stack, architecture diagram, demo gif
├─ WRITEUP.md                # the 1-page approach doc
├─ docker-compose.yml
├─ backend/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  ├─ app/
│  │  ├─ main.py             # FastAPI routes
│  │  ├─ session.py          # session lifecycle, DuckDB handle
│  │  ├─ ingest.py           # CSV/Excel → DuckDB tables
│  │  ├─ profile.py          # column profiling + join inference
│  │  ├─ llm.py              # provider abstraction (Groq | Ollama)
│  │  ├─ sql_guard.py        # sqlglot validation + repair loop
│  │  ├─ charts.py           # result-shape → chart spec
│  │  └─ prompts.py          # system prompt + few-shots
│  └─ tests/test_pipeline.py # ~8 golden Q→SQL→expected-number tests
├─ frontend/
│  ├─ app/page.tsx
│  ├─ components/{UploadZone,ChatPanel,ResultTable,ChartView,SqlPanel,SchemaSidebar}.tsx
│  └─ lib/api.ts
└─ sample-data/              # 3 related files: employees, departments, salaries
```

Ship `sample-data/` with joinable files. The demo question that lands hardest is a cross-file one:
*"What's the average salary per department, and which department grew headcount most in 2024?"*

---

## 6. Build schedule (6 hours)

| # | Time | Deliverable |
|---|---|---|
| 0 | 0:00–0:20 | Repo skeleton, docker-compose, sample data generated, Groq key |
| 1 | 0:20–1:10 | **Backend spine**: upload → DuckDB tables → `/schema` returns profiled columns. Test via curl. |
| 2 | 1:10–2:10 | **NL→SQL**: prompts, Groq call, sqlglot guard, execute, repair loop. Still curl-only. |
| 3 | 2:10–2:40 | Chart rule engine + NL summary call. `/ask` returns the full payload. |
| 4 | 2:40–4:00 | **Frontend**: upload zone, chat, result table, Recharts, SQL panel, schema sidebar |
| 5 | 4:00–4:40 | Join inference + prompt tuning against ~10 real questions. This is where accuracy is actually won. |
| 6 | 4:40–5:20 | Deploy (Vercel + Render), CORS, env vars, smoke test the hosted link |
| 7 | 5:20–6:00 | README + WRITEUP + 3-minute Loom demo |

**If you're running short, cut in this order:** join inference → NL summary call (just show the table) → Excel multi-sheet. **Never cut** the SQL transparency panel or the charts — those are criteria #3 and #4.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM writes SQL for columns that don't exist | sqlglot validation + one repair round; profiled schema in prompt makes it rare |
| Messy headers (spaces, unicode, dupes) | Normalize to `snake_case` on ingest, keep an original↔normalized map, show the original in the UI |
| Ambiguous question ("top performers") | Answer with an explicit stated assumption in the summary line: *"Interpreting 'top' as highest total sales."* Cheap, and reads as thoughtful. |
| Big file blows memory | Cap upload at 50 MB; DuckDB streams CSV anyway |
| Render cold start during panel demo | Warm it before the call; keep the video as backup |
| Free-tier rate limit mid-demo | Ollama fallback flag, switchable via env var |

---

## 8. "What I'd build next" (for the write-up)

- Conversation memory — follow-ups like *"now just for EMEA"* resolved against the previous SQL
- Saved/pinned questions → a lightweight dashboard
- Semantic layer: user-defined metric definitions (`attrition = ...`) so business terms map deterministically, no LLM guess
- Confidence signalling: run 2 sampled SQL generations, flag disagreement instead of asserting a wrong number
- Row-level security + tenant isolation (the real blocker for HR data in a Darwinbox context)
- Fine-tuned small local model for SQL, for on-prem customers who can't call an external API
```
