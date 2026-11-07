# ADR-002: Embedded SQLite Storage with aiosqlite and SQLModel

## Status
Accepted

## Context
The application needs local persistence for GitHub repository metadata, cached issues/PRs, check run history, and action execution logs. We compared an external database (PostgreSQL/MySQL) against an embedded database (SQLite).

## Decision
Use embedded SQLite via `aiosqlite` with SQLModel ORM. Schema migrations are omitted during active development; changing SQLModel definitions requires removing `grimoire.db` to recreate tables.

## Consequences
- **Positive:** Zero external infrastructure dependencies; ideal for single-node self-hosting and local development.
- **Negative:** SQLite allows exactly one writer, so concurrent writes serialize. All DB accesses are asynchronous and localized to short transaction blocks.

## Connection configuration
Every connection opened by `get_engine()` (`src/grimoire/database.py`) is configured with:

| Pragma | Value | Why |
|---|---|---|
| `journal_mode` | `WAL` | Readers and the writer proceed together. The rollback-journal default required an EXCLUSIVE lock to commit, so a concurrent writer could block every other writer for the whole `busy_timeout`. |
| `busy_timeout` | `15000` ms (`DEFAULT_BUSY_TIMEOUT_MS`, overridable) | pysqlite's 5 s default is too tight for a 10-repo refresh fan-out. |
| `synchronous` | `NORMAL` | Durable enough with WAL; avoids an fsync per commit. |

Write paths that must survive contention use `db_exec.retry_on_lock()`: the ETag
cache (best-effort — a persistent lock is a cache miss, never a failed fetch),
and `save_stats_to_db()` (a completed refresh is not discarded).

## Stress-Testing Evidence (grill-me)
- **Challenge:** Can SQLite handle concurrent check results writes from 5 parallel worker tasks?
- **Resolution:** Check results writes are batched per run record; WAL mode and `aiosqlite` connection serialization prevent database locking. Verified by failure-modes test suite in `tests/test_actions/test_engine_failure_modes.py`.
- **Correction (BUG-2026-11-07T000000):** the WAL claim above was aspirational — the pragma was never set, and the default rollback journal produced `database is locked` errors during refresh. WAL, `busy_timeout` and retry logic are now actually implemented and covered by `tests/test_database.py::test_engine_enables_wal_journal` and the lock-resilience tests in `tests/test_github/test_client.py`.
