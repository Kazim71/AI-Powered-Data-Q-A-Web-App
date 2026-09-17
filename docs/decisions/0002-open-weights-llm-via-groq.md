# 0002 · Open-weights LLM via Groq, Ollama as offline fallback

- **Status:** Accepted
- **Date:** 2026-09-17

## Context

The brief requires **open-source AI models**. Everything must run on free tiers. The model's
only job is text-to-SQL plus a one-sentence summary — a narrow task.

## Options considered

| Option | For | Against |
|---|---|---|
| **Groq API — `llama-3.3-70b-versatile`** | Open-weights model; generous free tier; very low latency; strong at SQL | External API; rate limits |
| **Ollama local — `qwen2.5-coder:7b`** | Fully offline; data-residency story | Needs RAM/GPU; free hosts can't run it well |
| Hugging Face Inference API | Many open models | Free tier is slow and cold-starts |
| Self-host on Oracle ARM VM | Truly free, private | Setup time; CPU inference is slow for 7B+ |
| OpenAI / Anthropic | Best quality | Not open-source — violates the brief |

## Decision

**Groq-hosted Llama 3.3 70B as the default, behind a provider interface, with Ollama as a
drop-in alternative** selected by the `LLM_PROVIDER` env var.

No agent framework: two prompts (SQL generation, answer summary) called with plain `httpx`.

## Consequences

**Positive**
- Meets the open-source requirement with a model large enough to write reliable SQL.
- Sub-second generation keeps the app feeling responsive.
- The provider interface lets the whole system run air-gapped with Ollama — a real selling
  point for HR/enterprise customers with data-residency constraints.
- Only schema metadata goes to the API, never row data ([0001](0001-nl-to-sql-over-duckdb.md)).

**Negative / accepted risks**
- Free-tier rate limits could interrupt a demo. Mitigation: Ollama fallback; demo video
  recorded locally.
- Sample values in the profile *are* real data points sent to the API. Acceptable for a
  prototype; a production version would make sampling opt-out per column.
