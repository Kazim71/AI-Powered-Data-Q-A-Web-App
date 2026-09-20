# 05 · Local development

## Prerequisites

- Python 3.11+ (developed on 3.12)
- Node 20+ *(frontend, milestone 3)*
- Docker *(optional)*

## Backend setup

```bash
cd backend
python -m venv .venv
```

Activate the virtualenv — Windows (Git Bash): `source .venv/Scripts/activate`,
macOS/Linux: `source .venv/bin/activate`. Then:

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

To ask questions (`/ask`), set `GROQ_API_KEY` in `.env` — a free key from
[console.groq.com](https://console.groq.com). Everything else (upload, schema, preview) works
without one. To run fully offline instead, install [Ollama](https://ollama.com), run
`ollama pull qwen2.5-coder:7b`, and set `LLM_PROVIDER=ollama`.

## Generate sample data

Two demo datasets, deliberately in different domains so correctness isn't an artifact of one
convenient shape of data:

```bash
python sample-data/generate.py              # HR: employees/departments/salaries (2-sheet workbook)
python sample-data/ecommerce/generate.py    # retail: customers/products/orders
```

## Run the server

From `backend/`:

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000/api
- Swagger UI: http://localhost:8000/docs

## Smoke test with curl

```bash
SID=$(curl -s -X POST localhost:8000/api/sessions | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
```

```bash
curl -s -X POST localhost:8000/api/sessions/$SID/files -F "files=@sample-data/employees.csv" -F "files=@sample-data/departments.csv" -F "files=@sample-data/salaries.xlsx"
```

```bash
curl -s -X POST localhost:8000/api/sessions/$SID/ask -H "Content-Type: application/json" -d '{"question": "Average base salary by department in 2024?"}'
```

## Tests

From `backend/`:

```bash
python -m pytest -q
```

Tests point `SESSION_DIR` at a temp directory before the app is imported, so they never touch
your real `.sessions/`. The API tests rely on `sample-data/` — they skip with a message if it
hasn't been generated. **No test calls a real LLM or the network** — `/ask` is tested against a
scripted `FakeLLMClient` (see `test_ask_api.py`), so the suite is fast and deterministic without
a `GROQ_API_KEY`.

| File | Covers |
|---|---|
| `tests/test_naming.py` | Header and table-name normalisation (pure functions) |
| `tests/test_ingestion_api.py` | Upload, multi-sheet, profiling, semantic types, joins, error paths |
| `tests/test_sql_guard.py` | Statement allow-list, function deny-list, table checks, row-cap injection |
| `tests/test_charts.py` | Every chart-selection rule against fixed result sets |
| `tests/test_llm_json_extraction.py` | Recovering JSON from markdown-fenced / preambled model output |
| `tests/test_ask_api.py` | Full `/ask` pipeline via a fake LLM: happy path, repair loop, rejected DROP, empty session, summary fallback |

## Docker

```bash
docker compose up --build
```

## Project layout

```
backend/
├─ app/
│  ├─ main.py              app factory, CORS, error handler
│  ├─ models.py            pydantic contract (API + LLM prompt)
│  ├─ api/routes.py        HTTP routes (thin)
│  ├─ core/
│  │  ├─ config.py         settings from env
│  │  ├─ errors.py         domain exceptions → status codes
│  │  └─ session.py        session registry + DuckDB handles
│  ├─ ingestion/
│  │  ├─ loader.py         files → tables
│  │  ├─ naming.py         identifier normalisation
│  │  ├─ profiler.py       column profiles + semantic types
│  │  ├─ joins.py          relationship inference
│  │  └─ catalog.py        schema assembly + cache
│  └─ query/
│     ├─ prompts.py        schema → LLM prompt text
│     ├─ llm.py            Groq | Ollama, one interface
│     ├─ sql_guard.py      allow-list validation, row cap
│     ├─ executor.py       async execution, timeout, truncation
│     ├─ charts.py         result shape → chart spec
│     └─ service.py        orchestrates ask() end to end
└─ tests/
```

## Known environment gotchas

### pip fails: "Could not find a suitable TLS CA certificate bundle"

Seen on Windows machines with PostgreSQL installed: its installer sets `SSL_CERT_FILE` /
`REQUESTS_CA_BUNDLE` to a path that may not exist, which breaks pip. Unset them for the shell:

```bash
unset SSL_CERT_FILE REQUESTS_CA_BUNDLE CURL_CA_BUNDLE
```

To fix permanently, remove or correct those variables in Windows environment settings.

### `/tmp` paths differ between Git Bash tools and Windows Python

On Windows, `curl -o /tmp/x.json` from Git Bash and `open('/tmp/x.json')` from Windows Python
resolve to different directories. Use an absolute Windows path when piping between them.
