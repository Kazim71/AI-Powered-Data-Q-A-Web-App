"""Shared fixtures.

SESSION_DIR is pointed at a temp directory *before* the app is imported, so the
test run never touches the developer's real .sessions folder.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest

os.environ["SESSION_DIR"] = tempfile.mkdtemp(prefix="dataqa-tests-")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA = REPO_ROOT / "sample-data"


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session_id(client: TestClient) -> str:
    response = client.post("/api/sessions")
    assert response.status_code == 200
    sid = response.json()["session_id"]
    yield sid
    client.delete(f"/api/sessions/{sid}")


@pytest.fixture(scope="session")
def sample_files() -> dict[str, Path]:
    files = {
        "employees": SAMPLE_DATA / "employees.csv",
        "departments": SAMPLE_DATA / "departments.csv",
        "salaries": SAMPLE_DATA / "salaries.xlsx",
    }
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        pytest.skip(f"Sample data missing, run sample-data/generate.py: {missing}")
    return files


def upload_files(
    client: TestClient, session_id: str, files: list[tuple[str, bytes]]
):
    """POST a batch of (filename, content) pairs to a session. Shared across
    test modules so every upload in the suite goes through one code path."""
    payload = [("files", (name, io.BytesIO(content))) for name, content in files]
    return client.post(f"/api/sessions/{session_id}/files", files=payload)


def upload_sample_files(
    client: TestClient, session_id: str, sample_files: dict[str, Path]
):
    return upload_files(
        client,
        session_id,
        [(p.name, p.read_bytes()) for p in sample_files.values()],
    )


@pytest.fixture
def populated_session_id(
    client: TestClient, session_id: str, sample_files: dict[str, Path]
) -> str:
    """A session with employees/departments/salaries already uploaded."""
    response = upload_sample_files(client, session_id, sample_files)
    assert response.status_code == 200
    return session_id
