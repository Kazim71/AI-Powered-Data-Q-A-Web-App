"""End-to-end tests of POST /ask, with a fake LLM client standing in for Groq/Ollama.

These pin down the orchestration in query/service.py — prompt building, SQL
validation, execution, the repair loop, and chart/answer assembly — without
any network call or real model. sql_guard.py and charts.py already have their
own focused unit tests; this file is about the pipeline wiring between them.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.errors import LLMError
from app.query import service as query_service


class FakeLLMClient:
    """Returns pre-scripted JSON responses in call order.

    Raises AssertionError if the pipeline asks for more responses than the
    test scripted — that's a signal the orchestration changed (e.g. an extra
    LLM round trip) and the test needs updating, not a silent pass.
    """

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, float]] = []

    async def complete_json(self, *, system: str, user: str, temperature: float) -> dict:
        self.calls.append((system, user, temperature))
        if not self._responses:
            raise AssertionError(
                f"FakeLLMClient received an unscripted call #{len(self.calls)}"
            )
        return self._responses.pop(0)


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch):
    """Patches the factory the service calls, and hands back a setter."""
    holder: dict[str, FakeLLMClient] = {}

    def _install(responses: list[dict]) -> FakeLLMClient:
        client = FakeLLMClient(responses)
        holder["client"] = client
        monkeypatch.setattr(query_service, "get_llm_client", lambda: client)
        return client

    yield _install


def test_ask_happy_path(client: TestClient, populated_session_id: str, fake_llm):
    fake_client = fake_llm(
        [
            {  # SQL generation
                "sql": "SELECT level, COUNT(*) AS headcount "
                "FROM employees GROUP BY level",
                "assumptions": [],
            },
            {"answer": "Level L1 has the most employees."},  # summary
        ]
    )

    response = client.post(
        f"/api/sessions/{populated_session_id}/ask",
        json={"question": "How many employees are at each level?"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["answer"] == "Level L1 has the most employees."
    assert "SELECT" in body["sql"].upper()
    assert body["columns"] == ["level", "headcount"]
    assert body["row_count"] == len(body["rows"])
    assert body["tables_used"] == ["employees"]
    assert body["repaired"] is False
    # A text category + one measure over 5 levels: pie (<=8 rows) or bar.
    assert body["chart"]["type"] in ("bar", "pie")
    assert len(fake_client.calls) == 2


def test_ask_repairs_once_on_invalid_column(
    client: TestClient, populated_session_id: str, fake_llm
):
    fake_llm(
        [
            {  # first attempt references a column that doesn't exist
                "sql": "SELECT nonexistent_column FROM employees",
                "assumptions": [],
            },
            {  # repair call, given the DB error, fixes it
                "sql": "SELECT full_name FROM employees LIMIT 5",
                "assumptions": [],
            },
            {"answer": "Here are five employee names."},  # summary
        ]
    )

    response = client.post(
        f"/api/sessions/{populated_session_id}/ask",
        json={"question": "List some employee names"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["repaired"] is True
    assert body["columns"] == ["full_name"]


def test_ask_fails_cleanly_after_repair_also_fails(
    client: TestClient, populated_session_id: str, fake_llm
):
    fake_llm(
        [
            {"sql": "SELECT nonexistent_a FROM employees", "assumptions": []},
            {"sql": "SELECT nonexistent_b FROM employees", "assumptions": []},
        ]
    )

    response = client.post(
        f"/api/sessions/{populated_session_id}/ask",
        json={"question": "This will never work"},
    )
    assert response.status_code == 422
    assert "error" in response.json()


def test_ask_rejects_non_select_sql_without_touching_the_database(
    client: TestClient, populated_session_id: str, fake_llm
):
    fake_llm(
        [
            {"sql": "DROP TABLE employees", "assumptions": []},
            {"sql": "SELECT count(*) AS n FROM employees", "assumptions": []},
            {"answer": "There are 120 employees."},
        ]
    )

    response = client.post(
        f"/api/sessions/{populated_session_id}/ask",
        json={"question": "Delete everything"},
    )
    # The guard rejects the DROP before it ever reaches DuckDB, and the
    # service treats that exactly like any other failed attempt: one repair.
    assert response.status_code == 200
    assert response.json()["repaired"] is True

    # The table must still exist and be intact.
    preview = client.get(
        f"/api/sessions/{populated_session_id}/tables/employees/preview"
    )
    assert preview.status_code == 200


def test_ask_on_empty_session_returns_400(client: TestClient, session_id: str, fake_llm):
    fake_llm([])  # the LLM must never be called for an empty session
    response = client.post(
        f"/api/sessions/{session_id}/ask", json={"question": "Anything?"}
    )
    assert response.status_code == 400


def test_ask_surfaces_assumptions(client: TestClient, populated_session_id: str, fake_llm):
    fake_llm(
        [
            {
                "sql": "SELECT full_name, performance_rating FROM employees "
                "ORDER BY performance_rating DESC LIMIT 5",
                "assumptions": ["Interpreting 'top' as highest performance_rating"],
            },
            {"answer": "The top performer is listed first."},
        ]
    )

    response = client.post(
        f"/api/sessions/{populated_session_id}/ask",
        json={"question": "Who are the top performers?"},
    )
    body = response.json()
    assert body["assumptions"] == ["Interpreting 'top' as highest performance_rating"]


def test_ask_falls_back_to_a_plain_answer_when_summary_call_fails(
    client: TestClient, populated_session_id: str, monkeypatch: pytest.MonkeyPatch
):
    """A successful query shouldn't be discarded just because the second
    (summary) LLM call fails — e.g. a rate limit hit after SQL generation
    already succeeded."""

    class FlakySummaryClient:
        def __init__(self) -> None:
            self.call_count = 0

        async def complete_json(self, *, system: str, user: str, temperature: float) -> dict:
            self.call_count += 1
            if self.call_count == 1:
                return {"sql": "SELECT count(*) AS n FROM employees", "assumptions": []}
            raise LLMError("rate limited")

    monkeypatch.setattr(
        query_service, "get_llm_client", lambda: FlakySummaryClient()
    )

    response = client.post(
        f"/api/sessions/{populated_session_id}/ask",
        json={"question": "How many employees are there?"},
    )
    assert response.status_code == 200
    assert "1 row" in response.json()["answer"]


def test_ask_question_too_long_is_rejected(client: TestClient, populated_session_id: str):
    response = client.post(
        f"/api/sessions/{populated_session_id}/ask",
        json={"question": "x" * 3000},
    )
    assert response.status_code == 422  # pydantic validation, before any LLM call


def test_ask_empty_question_is_rejected(client: TestClient, populated_session_id: str):
    response = client.post(
        f"/api/sessions/{populated_session_id}/ask", json={"question": ""}
    )
    assert response.status_code == 422
