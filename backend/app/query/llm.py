"""LLM provider abstraction.

Two implementations behind one interface, chosen by `LLM_PROVIDER`:
  * GroqClient   — hosted, OpenAI-compatible endpoint, open-weights Llama 3.3
  * OllamaClient — fully local, no data or schema leaves the machine

Neither prompts.py nor the query service knows which one is in use. See
docs/decisions/0002-open-weights-llm-via-groq.md for why both exist.

Every model, even ones asked nicely for "JSON only", occasionally wraps its
answer in a markdown fence or adds a stray sentence. `_extract_json` is the
single place that defends against that, so callers can trust a clean dict.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.errors import LLMError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Best-effort recovery of a JSON object from a model's raw reply."""
    text = text.strip()

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: the outermost {...}, in case the model added a preamble.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise LLMError(
        "The model's response could not be parsed as JSON.",
        detail=text[:500],
    )


class LLMClient(Protocol):
    async def complete_json(
        self, *, system: str, user: str, temperature: float
    ) -> dict:
        """Send a chat completion request and return the parsed JSON object."""
        ...


class GroqClient:
    """OpenAI-compatible chat completions endpoint, hosted by Groq."""

    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise LLMError(
                "GROQ_API_KEY is not set.",
                detail="Set it in backend/.env, or set LLM_PROVIDER=ollama to run "
                "fully locally instead.",
            )

    async def complete_json(
        self, *, system: str, user: str, temperature: float
    ) -> dict:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{settings.groq_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json={
                        "model": settings.groq_model,
                        "temperature": temperature,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
            except httpx.TimeoutException as exc:
                raise LLMError(
                    "The AI model took too long to respond.", detail=str(exc)
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(
                    "Could not reach the AI model provider (Groq).", detail=str(exc)
                ) from exc

        if response.status_code == 429:
            raise LLMError(
                "The AI model's free-tier rate limit was hit. Try again shortly, "
                "or set LLM_PROVIDER=ollama to run locally.",
                detail=response.text[:500],
            )
        if response.status_code != 200:
            raise LLMError(
                "The AI model provider returned an error.",
                detail=f"HTTP {response.status_code}: {response.text[:500]}",
            )

        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(
                "The AI model provider returned an unexpected response shape.",
                detail=str(body)[:500],
            ) from exc

        return _extract_json(content)


class OllamaClient:
    """A local Ollama server's native /api/chat endpoint.

    Used over Ollama's OpenAI-compatibility layer because /api/chat has been
    stable across Ollama versions for longer, and `format: "json"` is a
    first-class, well-supported option on it.
    """

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")

    async def complete_json(
        self, *, system: str, user: str, temperature: float
    ) -> dict:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": temperature},
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
            except httpx.TimeoutException as exc:
                raise LLMError(
                    "The local AI model took too long to respond.", detail=str(exc)
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(
                    "Could not reach Ollama.",
                    detail=f"{exc} — is `ollama serve` running at {self._base_url}?",
                ) from exc

        if response.status_code != 200:
            raise LLMError(
                "Ollama returned an error.",
                detail=f"HTTP {response.status_code}: {response.text[:500]}",
            )

        body = response.json()
        try:
            content = body["message"]["content"]
        except KeyError as exc:
            raise LLMError(
                "Ollama returned an unexpected response shape.",
                detail=str(body)[:500],
            ) from exc

        return _extract_json(content)


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaClient()
    if settings.llm_provider == "groq":
        return GroqClient()
    raise LLMError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'.",
        detail="Expected 'groq' or 'ollama'.",
    )
