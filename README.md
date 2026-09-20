# AI-Powered Data Q&A

Upload CSV and Excel files, ask analytical questions in plain English, get correct answers
with charts — and see the exact SQL behind every number.

> Darwinbox Forward Deployed Engineer take-home.

## How it works

The LLM never sees your data, only a **profile** of it. It writes SQL; **DuckDB computes the
answer**. So numbers are calculated rather than generated, prompts stay small regardless of
file size, and every answer can be audited.

```
files ──▶ normalise ──▶ profile columns ──▶ infer joins ──▶ cached schema
                                                                │
question ──▶ open-weights LLM ──▶ SQL ──▶ validate ──▶ DuckDB ──▶ answer + chart + SQL
```

What sits on top of the raw LLM output:

- **Column profiling** — semantic types, value ranges, and complete category lists, so the
  model filters on `'EMEA'` rather than inventing `'Europe'`, and never sums an ID
- **Measured join inference** — relationships across files confirmed by real value overlap
- **SQL guardrails** — allow-list on statement shape (SELECT-only, not a keyword blocklist), a
  function deny-list against reading outside the uploaded tables, and a one-shot self-repair
  loop that feeds the exact DuckDB error back to the model
- **Deterministic charts** — picked from the executed result's shape, so they can't be
  hallucinated and can never reference a column that isn't actually there

## Status

| Milestone | |
|---|---|
| M1 · Ingestion backend — upload, profiling, join inference | ✅ 26 tests |
| M2 · Question answering — NL → SQL, guardrails, charts | ✅ 76 tests, verified against a real Groq model |
| M3 · Frontend | ✅ builds clean, not yet click-through tested in a browser |
| M4 · Deploy + write-up | ⏳ |

All four acceptance criteria in the brief are met end to end. Try the API via `/docs` (below),
the app via `npm run dev` in [frontend/](frontend), or see the full request/response shapes in
[docs/04-api-reference.md](docs/04-api-reference.md).

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI · Python 3.12 |
| Analytics engine | DuckDB |
| File parsing | DuckDB CSV reader · pandas + openpyxl |
| LLM | gpt-oss-120b via Groq · Ollama for offline |
| SQL validation | sqlglot |
| Frontend | Next.js 16 · TypeScript · Tailwind v4 · Recharts |
| Hosting | Render (API) · Vercel (web) |

## Quick start

```bash
cd backend && python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt
```

```bash
python sample-data/generate.py
```

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive API. To ask questions, add a free key from
[console.groq.com](https://console.groq.com) to `backend/.env` as `GROQ_API_KEY` (or set
`LLM_PROVIDER=ollama` to run fully locally — see [.env.example](backend/.env.example)). Full
guide: [docs/05-local-development.md](docs/05-local-development.md).

Or with Docker (backend only — see [frontend/README.md](frontend/README.md) for the app):

```bash
docker compose up --build
```

Then, in a second terminal, the frontend:

```bash
cd frontend && npm install && cp .env.example .env.local && npm run dev
```

Open http://localhost:3000.

## Repository layout

```
├─ backend/          FastAPI service
│  ├─ app/
│  │  ├─ api/        HTTP routes
│  │  ├─ core/       config, errors, sessions
│  │  ├─ ingestion/  load → normalise → profile → join inference
│  │  └─ query/      question → SQL → validate → execute → chart → answer
│  └─ tests/         76 tests, no network calls
├─ frontend/         Next.js app — the workspace UI (upload, ask, answer/chart/table/SQL)
├─ sample-data/      generator for 3 related demo files
└─ docs/             architecture, API, decisions, progress log
```

## Documentation

Start at **[docs/README.md](docs/README.md)**. Highlights:

- [Architecture](docs/02-architecture.md)
- [Data pipeline](docs/03-data-pipeline.md)
- [API reference](docs/04-api-reference.md)
- [Decision records](docs/decisions/README.md) — why each major choice was made
- [Progress log](docs/07-progress-log.md) — including bugs caught during verification
