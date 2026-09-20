"""End-to-end tests of the ingestion pipeline through the HTTP API.

These pin down the behaviour the LLM layer will depend on: correct tables,
correct semantic types, and correct join hints. If one of these regresses,
answer quality regresses with it.
"""

from __future__ import annotations

from tests.conftest import upload_files as _upload
from tests.conftest import upload_sample_files as _upload_samples


def _columns(schema: dict, table: str) -> dict[str, dict]:
    match = next(t for t in schema["tables"] if t["name"] == table)
    return {c["name"]: c for c in match["columns"]}


# --- Upload & table creation ----------------------------------------------


def test_multi_file_upload_creates_one_table_per_file_and_sheet(
    client, session_id, sample_files
):
    response = _upload_samples(client, session_id, sample_files)
    assert response.status_code == 200
    body = response.json()

    assert all(f["status"] == "ok" for f in body["files"])
    tables = {t["name"]: t for t in body["schema"]["tables"]}
    # The two-sheet workbook must produce two tables, not one.
    assert set(tables) == {"employees", "departments", "salaries_2023", "salaries_2024"}
    assert tables["salaries_2023"]["sheet_name"] == "2023"
    assert tables["employees"]["row_count"] == 120


def test_messy_headers_are_normalised_but_originals_kept(
    client, session_id, sample_files
):
    body = _upload_samples(client, session_id, sample_files).json()
    cols = _columns(body["schema"], "salaries_2023")

    assert "base_salary_inr" in cols
    assert cols["base_salary_inr"]["original_name"] == "Base Salary (INR)"


# --- Profiling ------------------------------------------------------------


def test_semantic_types(client, session_id, sample_files):
    body = _upload_samples(client, session_id, sample_files).json()
    emp = _columns(body["schema"], "employees")

    assert emp["employee_id"]["semantic_type"] == "identifier"
    # A repeating foreign key is still an identifier — never a measure.
    assert emp["department_id"]["semantic_type"] == "identifier"
    assert emp["hire_date"]["semantic_type"] == "temporal"
    assert emp["is_active"]["semantic_type"] == "boolean"
    assert emp["level"]["semantic_type"] == "categorical"
    # A 1-5 rating stays numeric so it can be averaged...
    assert emp["performance_rating"]["semantic_type"] == "numeric"
    # ...but still exposes its values, so filters use real ones.
    assert emp["performance_rating"]["categories"] == [2.0, 3.0, 4.0, 5.0]


def test_categoricals_expose_full_value_list(client, session_id, sample_files):
    body = _upload_samples(client, session_id, sample_files).json()
    levels = _columns(body["schema"], "employees")["level"]["categories"]
    assert levels == ["L1", "L2", "L3", "L4", "L5"]


def test_numeric_and_temporal_ranges(client, session_id, sample_files):
    body = _upload_samples(client, session_id, sample_files).json()
    emp = _columns(body["schema"], "employees")
    assert emp["hire_date"]["min_value"] is not None
    assert emp["hire_date"]["min_value"] <= emp["hire_date"]["max_value"]


# --- Join inference -------------------------------------------------------


def test_join_hints_find_real_relationships(client, session_id, sample_files):
    body = _upload_samples(client, session_id, sample_files).json()
    joins = {
        frozenset({
            (h["left_table"], h["left_column"]),
            (h["right_table"], h["right_column"]),
        })
        for h in body["schema"]["join_hints"]
    }

    assert frozenset({("departments", "id"), ("employees", "department_id")}) in joins
    assert frozenset(
        {("employees", "employee_id"), ("salaries_2023", "employee_id")}
    ) in joins


def test_constant_columns_do_not_produce_join_noise(client, session_id, sample_files):
    body = _upload_samples(client, session_id, sample_files).json()
    joined_columns = {
        col
        for h in body["schema"]["join_hints"]
        for col in (h["left_column"], h["right_column"])
    }
    # `currency` is 'INR' in every row of both salary sheets: not a key.
    assert "currency" not in joined_columns


# --- Failure handling -----------------------------------------------------


def test_partial_success_on_mixed_upload(client, session_id):
    response = _upload(
        client,
        session_id,
        [
            ("notes.pdf", b"%PDF-1.4 not a table"),
            ("regions.csv", b"Region,Revenue\nEMEA,100\nAPAC,250\n"),
        ],
    )
    assert response.status_code == 200
    results = {f["filename"]: f for f in response.json()["files"]}

    assert results["notes.pdf"]["status"] == "failed"
    assert "not a supported file type" in results["notes.pdf"]["error"]
    assert results["regions.csv"]["status"] == "ok"
    assert results["regions.csv"]["tables"] == ["regions"]


def test_same_filename_twice_does_not_clobber(client, session_id):
    csv = b"a,b\n1,2\n"
    _upload(client, session_id, [("data.csv", csv)])
    body = _upload(client, session_id, [("data.csv", csv)]).json()
    assert body["files"][0]["tables"] == ["data_2"]


def test_unknown_session_is_404(client):
    response = client.get("/api/sessions/does-not-exist/schema")
    assert response.status_code == 404
    assert "error" in response.json()


def test_unknown_table_preview_is_404(client, session_id):
    response = client.get(f"/api/sessions/{session_id}/tables/nope/preview")
    assert response.status_code == 404


def test_preview_returns_rows(client, session_id, sample_files):
    _upload_samples(client, session_id, sample_files)
    body = client.get(
        f"/api/sessions/{session_id}/tables/departments/preview?limit=2"
    ).json()
    assert body["columns"] == ["id", "department_name", "location", "function"]
    assert len(body["rows"]) == 2
