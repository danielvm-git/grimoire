# ADR-002: Embedded SQLite Storage with aiosqlite and SQLModel

## Status
Accepted

## Context
The application needs local persistence for GitHub repository metadata, cached issues/PRs, check run history, and action execution logs. We compared an external database (PostgreSQL/MySQL) against an embedded database (SQLite).

## Decision
Use embedded SQLite via `aiosqlite` with SQLModel ORM. Schema migrations are omitted during active development; changing SQLModel definitions requires removing `grimoire.db` to recreate tables.

## Consequences
- **Positive:** Zero external infrastructure dependencies; ideal for single-node self-hosting and local development.
- **Negative:** Concurrency writes must be sequential to avoid SQLITE_BUSY locks. All DB accesses are asynchronous and localized to short transaction blocks.

## Stress-Testing Evidence (grill-me)
- **Challenge:** Can SQLite handle concurrent check results writes from 5 parallel worker tasks?
- **Resolution:** Check results writes are batched per run record; WAL mode and `aiosqlite` connection serialization prevent database locking. Verified by failure-modes test suite in `tests/test_actions/test_engine_failure_modes.py`.
