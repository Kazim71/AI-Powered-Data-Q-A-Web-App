# 0004 · Ephemeral per-session DuckDB files, in-process registry

- **Status:** Accepted
- **Date:** 2026-09-17

## Context

Users upload files and ask questions within one sitting. No accounts are required. Hosting is
a free-tier single instance with an ephemeral disk.

## Options considered

| Option | For | Against |
|---|---|---|
| One shared in-memory DuckDB | Simplest | Users' tables collide; no isolation |
| In-memory DuckDB per session | Isolated | Lost if the worker restarts; harder to debug |
| **DuckDB file per session + in-process registry** | Isolated; inspectable on disk; no extra services | Single-instance only |
| Postgres + Redis | Scales horizontally | Two more services to host free; overkill |

## Decision

Each session gets `.sessions/<id>/` holding `uploads/` and `data.duckdb`. A thread-safe
in-process `SessionRegistry` maps ids to open connections. Sessions expire after
`SESSION_TTL_MINUTES` (default 120) of inactivity.

Session ids are generated server-side (UUID4 hex), so user input never builds a filesystem path.

## Consequences

**Positive**
- Complete data isolation between users with zero tenancy code.
- A misbehaving session can be debugged by opening its `.duckdb` file directly.
- Matches the ephemeral disk on Render's free tier instead of fighting it.

**Negative / accepted risks**
- **Must run as a single worker / instance.** Scaling out requires a shared registry
  (Redis) and shared storage — listed in the [roadmap](../08-roadmap.md).
- A server restart drops all sessions; users re-upload. Acceptable for a prototype.
- `purge_expired` exists but is not yet scheduled; add a background task before real traffic.
