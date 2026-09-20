"""Unit tests for defensive JSON parsing of raw model output.

Models asked for "JSON only" still sometimes wrap it in a markdown fence or
add a stray sentence — this is the one place that recovers from that.
"""

from __future__ import annotations

import pytest

from app.core.errors import LLMError
from app.query.llm import _extract_json


def test_clean_json_object() -> None:
    assert _extract_json('{"sql": "SELECT 1"}') == {"sql": "SELECT 1"}


def test_json_wrapped_in_markdown_fence() -> None:
    text = '```json\n{"sql": "SELECT 1"}\n```'
    assert _extract_json(text) == {"sql": "SELECT 1"}


def test_json_wrapped_in_bare_fence() -> None:
    text = '```\n{"sql": "SELECT 1"}\n```'
    assert _extract_json(text) == {"sql": "SELECT 1"}


def test_json_with_preamble_text() -> None:
    text = 'Here is the query:\n{"sql": "SELECT 1"}'
    assert _extract_json(text) == {"sql": "SELECT 1"}


def test_json_with_surrounding_whitespace() -> None:
    assert _extract_json('  \n {"sql": "SELECT 1"}  \n') == {"sql": "SELECT 1"}


def test_unparseable_text_raises_llm_error() -> None:
    with pytest.raises(LLMError):
        _extract_json("I cannot answer that.")
