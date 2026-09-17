"""HTTP routes.

Kept thin on purpose: every route validates input, delegates to the ingestion
or query layer, and shapes a response. No business logic lives here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from app.core.config import settings
from app.core.errors import (
    FileTooLarge,
    IngestionError,
    TableNotFound,
    TooManyFiles,
    UnsupportedFileType,
)
from app.core.session import registry
from app.ingestion import catalog
from app.ingestion.loader import is_supported, load_file
from app.models import (
    SessionCreatedResponse,
    SessionSchema,
    UploadedFileResult,
    UploadResponse,
)

router = APIRouter()


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/sessions", response_model=SessionCreatedResponse, tags=["session"])
def create_session() -> SessionCreatedResponse:
    """Start a session. Returns the id used by every subsequent call."""
    session = registry.create()
    return SessionCreatedResponse(session_id=session.id, created_at=session.created_at)


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    response_class=Response,
    tags=["session"],
)
def delete_session(session_id: str) -> Response:
    """Drop a session and delete its uploaded files and database."""
    catalog.forget(session_id)
    registry.delete(session_id)
    return Response(status_code=204)


@router.post(
    "/sessions/{session_id}/files", response_model=UploadResponse, tags=["data"]
)
async def upload_files(
    session_id: str, files: list[UploadFile] = File(...)
) -> UploadResponse:
    """Upload one or more CSV/Excel files into a session.

    Partial success is intentional: one bad file should not discard the good
    ones. Each file reports its own status and the tables it produced.
    """
    session = registry.get(session_id)

    existing = len(session.table_names())
    if existing + len(files) > settings.max_files_per_session:
        raise TooManyFiles(
            f"A session holds at most {settings.max_files_per_session} tables; "
            f"it already has {existing}."
        )

    results: list[UploadedFileResult] = []

    for upload in files:
        filename = upload.filename or "unnamed"
        try:
            if not is_supported(filename):
                raise UnsupportedFileType(
                    f"'{filename}' is not a supported file type. "
                    "Upload a .csv, .tsv, .xlsx or .xls file."
                )

            destination = session.upload_dir / Path(filename).name
            size = 0
            with destination.open("wb") as sink:
                # Stream in chunks so a large upload never sits in memory whole,
                # and abort as soon as the cap is exceeded.
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        sink.close()
                        destination.unlink(missing_ok=True)
                        raise FileTooLarge(
                            f"'{filename}' exceeds the "
                            f"{settings.max_upload_mb} MB limit."
                        )
                    sink.write(chunk)

            loaded = load_file(session, destination, filename)
            for item in loaded:
                catalog.record_provenance(
                    session, item.table, item.source_file, item.sheet_name
                )
            results.append(
                UploadedFileResult(
                    filename=filename,
                    status="ok",
                    tables=[item.table for item in loaded],
                )
            )

        except (UnsupportedFileType, FileTooLarge, IngestionError) as exc:
            results.append(
                UploadedFileResult(
                    filename=filename, status="failed", error=exc.message
                )
            )
        finally:
            await upload.close()

    # Re-profile once, after all files have landed, so join inference sees the
    # complete picture rather than running per file.
    schema = catalog.build_schema(session)

    return UploadResponse(session_id=session.id, files=results, schema_=schema)


@router.get(
    "/sessions/{session_id}/schema", response_model=SessionSchema, tags=["data"]
)
def get_schema(session_id: str, refresh: bool = False) -> SessionSchema:
    """The profiled catalogue: tables, column profiles and inferred joins.

    This is both the sidebar's data source and the context handed to the LLM.
    """
    session = registry.get(session_id)
    return catalog.get_schema(session, refresh=refresh)


@router.get("/sessions/{session_id}/tables/{table}/preview", tags=["data"])
def preview_table(session_id: str, table: str, limit: int = 20) -> dict:
    """First N rows of a table, for the UI's data preview."""
    session = registry.get(session_id)
    # Membership check against the real catalogue is also what makes the
    # f-string below safe: `table` can only ever be a name DuckDB gave us.
    if table not in session.table_names():
        raise TableNotFound(f"Table '{table}' does not exist in this session.")

    limit = max(1, min(limit, 200))
    cursor = session.connection.execute(f'SELECT * FROM "{table}" LIMIT {limit}')
    columns = [d[0] for d in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return {"table": table, "columns": columns, "rows": rows}
