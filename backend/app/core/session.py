"""Session lifecycle: one DuckDB database and one upload directory per session.

Why a DuckDB *file* rather than an in-memory database: it survives the worker
process, it is trivially inspectable when debugging ("just open the .duckdb"),
and it keeps each user's tables isolated without any multi-tenant logic.

This registry is in-process and therefore single-worker. That is a deliberate
prototype constraint, documented in docs/decisions/0004-session-model.md.
"""

from __future__ import annotations

import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

from app.core.config import settings
from app.core.errors import SessionNotFound


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Session:
    id: str
    directory: Path
    created_at: datetime
    last_used_at: datetime
    connection: duckdb.DuckDBPyConnection
    # table name -> {clean column: original header}, for display in the UI.
    column_labels: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def upload_dir(self) -> Path:
        return self.directory / "uploads"

    def touch(self) -> None:
        self.last_used_at = _utcnow()

    def table_names(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        try:
            self.connection.close()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass


class SessionRegistry:
    """Thread-safe store of live sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        directory = settings.session_dir / session_id
        (directory / "uploads").mkdir(parents=True, exist_ok=True)

        connection = duckdb.connect(str(directory / "data.duckdb"))
        now = _utcnow()
        session = Session(
            id=session_id,
            directory=directory,
            created_at=now,
            last_used_at=now,
            connection=connection,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(
                f"Session '{session_id}' not found. It may have expired — "
                "upload your files again to start a new one."
            )
        session.touch()
        return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return
        session.close()
        shutil.rmtree(session.directory, ignore_errors=True)

    def purge_expired(self) -> int:
        """Drop sessions idle for longer than the TTL. Returns count removed."""
        cutoff = _utcnow() - timedelta(minutes=settings.session_ttl_minutes)
        with self._lock:
            stale = [s.id for s in self._sessions.values() if s.last_used_at < cutoff]
        for session_id in stale:
            self.delete(session_id)
        return len(stale)

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()


registry = SessionRegistry()
