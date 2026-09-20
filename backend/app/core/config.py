"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Storage -------------------------------------------------------
    # One directory per session, holding the uploaded files and the DuckDB
    # database. Ephemeral by design: on Render's free tier this disk is wiped
    # on restart, which matches our "sessions are disposable" model.
    session_dir: Path = BACKEND_ROOT / ".sessions"
    session_ttl_minutes: int = 120

    # --- Upload limits -------------------------------------------------
    max_upload_mb: int = 50
    max_files_per_session: int = 10

    # --- Profiling -----------------------------------------------------
    # How many distinct example values to show the LLM per column. Enough to
    # convey meaning ("EMEA", "APAC"), small enough to keep the prompt cheap.
    profile_sample_values: int = 5
    # Columns with at most this many distinct values are treated as categorical
    # and get their full value list surfaced in the schema context.
    categorical_max_cardinality: int = 25

    # --- Query execution ----------------------------------------------
    max_result_rows: int = 1000
    query_timeout_seconds: int = 30

    # --- CORS ----------------------------------------------------------
    cors_origins: str = "http://localhost:3000"

    # --- LLM -------------------------------------------------------------
    # "groq" (hosted, free-tier, open-weights Llama) or "ollama" (fully local
    # — no data or schema metadata leaves the machine). See
    # docs/decisions/0002-open-weights-llm-via-groq.md.
    llm_provider: str = "groq"

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"

    llm_timeout_seconds: int = 20
    # SQL generation is deterministic-ish; the summary call can be a little
    # freer without risking a different query shape.
    llm_temperature_sql: float = 0.0
    llm_temperature_summary: float = 0.3

    # A single self-repair round trip on a SQL execution error. Kept at 1:
    # more retries burn latency and free-tier quota for diminishing returns.
    sql_repair_attempts: int = 1

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
settings.session_dir.mkdir(parents=True, exist_ok=True)
