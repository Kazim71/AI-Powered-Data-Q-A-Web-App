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

## Generate sample data

Three related, deliberately messy files (untidy headers, a foreign key, a two-sheet workbook):

```bash
python sample-data/generate.py
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

## Tests

From `backend/`:

```bash
python -m pytest -q
```

Tests point `SESSION_DIR` at a temp directory before the app is imported, so they never touch
your real `.sessions/`. The API tests rely on `sample-data/` — they skip with a message if it
hasn't been generated.

| File | Covers |
|---|---|
| `tests/test_naming.py` | Header and table-name normalisation (pure functions) |
| `tests/test_ingestion_api.py` | Upload, multi-sheet, profiling, semantic types, joins, error paths |

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
│  └─ ingestion/
│     ├─ loader.py         files → tables
│     ├─ naming.py         identifier normalisation
│     ├─ profiler.py       column profiles + semantic types
│     ├─ joins.py          relationship inference
│     └─ catalog.py        schema assembly + cache
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
