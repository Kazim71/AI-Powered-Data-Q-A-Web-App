# 08 · Roadmap

## Milestones

### ✅ M1 — Ingestion backend
Upload, normalise, profile, infer joins, cache schema. 26 tests.

### ⏳ M2 — Question answering (`/ask`)
- [ ] `query/prompts.py` — render `SessionSchema` into a compact prompt with join hints and
      few-shot examples
- [ ] `query/llm.py` — provider interface; Groq and Ollama implementations, chosen by env var
- [ ] `query/sql_guard.py` — sqlglot parse; single `SELECT`/`WITH` only; table and column
      existence; enforced `LIMIT`
- [ ] Execution with statement timeout and row cap
- [ ] Repair loop: one retry feeding the DuckDB error back to the model
- [ ] `query/charts.py` — result shape → chart spec
- [ ] One-sentence natural-language answer from the result
- [ ] Golden tests: ~10 questions with known correct numbers on sample data

### ⏳ M3 — Frontend
- [ ] Next.js + Tailwind + shadcn/ui scaffold
- [ ] Drag-and-drop multi-file upload with per-file status
- [ ] Schema sidebar: tables, columns with semantic-type badges, join hints
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
