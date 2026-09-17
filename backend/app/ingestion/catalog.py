"""Builds and caches the session catalogue (profiles + join hints).

Profiling costs a table scan, so we compute it once per upload and cache it on
the session. `/ask` will read this cache on every question — it must be cheap.
"""

from __future__ import annotations

from app.core.session import Session
from app.ingestion.joins import infer_joins
from app.ingestion.profiler import profile_table
from app.models import SessionSchema, TableProfile

# session id -> cached schema
_cache: dict[str, SessionSchema] = {}
# session id -> {table: (source_file, sheet_name)}
_provenance: dict[str, dict[str, tuple[str, str | None]]] = {}


def record_provenance(
    session: Session, table: str, source_file: str, sheet_name: str | None
) -> None:
    _provenance.setdefault(session.id, {})[table] = (source_file, sheet_name)


def invalidate(session_id: str) -> None:
    _cache.pop(session_id, None)


def forget(session_id: str) -> None:
    _cache.pop(session_id, None)
    _provenance.pop(session_id, None)


def build_schema(session: Session) -> SessionSchema:
    """Profile every table in the session and infer joins between them."""
    provenance = _provenance.get(session.id, {})
    tables: list[TableProfile] = []

    for table in session.table_names():
        source_file, sheet_name = provenance.get(table, (table, None))
        tables.append(profile_table(session, table, source_file, sheet_name))

    schema = SessionSchema(
        session_id=session.id,
        created_at=session.created_at,
        tables=tables,
        join_hints=infer_joins(session, tables) if len(tables) > 1 else [],
    )
    _cache[session.id] = schema
    return schema


def get_schema(session: Session, *, refresh: bool = False) -> SessionSchema:
    if not refresh and session.id in _cache:
        return _cache[session.id]
    return build_schema(session)
