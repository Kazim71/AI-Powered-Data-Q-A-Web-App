"""Shared fixtures.

SESSION_DIR is pointed at a temp directory *before* the app is imported, so the
test run never touches the developer's real .sessions folder.
"""

from __future__ import annotations

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
