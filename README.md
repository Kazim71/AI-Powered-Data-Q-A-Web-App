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
- **SQL guardrails** — read-only validation and a self-repair loop *(in progress)*
- **Deterministic charts** — picked from the result's shape, so they can't be hallucinated *(in progress)*

## Status

| Milestone | |
|---|---|
| M1 · Ingestion backend — upload, profiling, join inference | ✅ 26 tests passing |
| M2 · Question answering — NL → SQL, guardrails, charts | ⏳ |
| M3 · Frontend | ⏳ |
| M4 · Deploy + write-up | ⏳ |

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI · Python 3.12 |
| Analytics engine | DuckDB |
| File parsing | DuckDB CSV reader · pandas + openpyxl |
| LLM | Llama 3.3 70B via Groq · Ollama for offline |
| SQL validation | sqlglot |
| Frontend | Next.js · Tailwind · shadcn/ui · Recharts |
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

Open http://localhost:8000/docs for the interactive API. Full guide:
[docs/05-local-development.md](docs/05-local-development.md).

Or with Docker:

```bash
docker compose up --build
```

## Repository layout

```
├─ backend/          FastAPI service
│  ├─ app/
│  │  ├─ api/        HTTP routes
│  │  ├─ core/       config, errors, sessions
│  │  └─ ingestion/  load → normalise → profile → join inference
│  └─ tests/
├─ frontend/         Next.js app (milestone 3)
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
