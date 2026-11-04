"""SQLModel table definitions and database engine setup."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, or_, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.db_exec import exec_raw
from grimoire.state import (
    ALL_RUN_STATES,
    TERMINAL_RUN_STATES,
    RunState,
)

logger = logging.getLogger(__name__)

# A running run owns a lease for this long; the engine refreshes it via
# ``start_run_heartbeat`` while the script executes.
RUN_LEASE_SECONDS = 60

# Identifies this process as the lease owner of the runs it starts.
PROCESS_OWNER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Check results
# ---------------------------------------------------------------------------


class CheckRunRecord(SQLModel, table=True):
    """Metadata for a complete check run (one execution across all targets)."""

    __tablename__ = "check_run"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    check_slug: str = Field(index=True)
    check_name: str
    triggered_by: str  # "manual" | "cron" | "refresh"
    # queued | running | completed | failed | interrupted (see grimoire.state)
    status: str = RunState.QUEUED.value
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None
    owner_id: str = Field(default="", index=True)
    heartbeat_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None


class CheckResultRecord(SQLModel, table=True):
    """Persistent record of a single check execution."""

    __tablename__ = "check_result"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    run_id: int | None = Field(default=None, index=True, foreign_key="check_run.id")
    check_slug: str = Field(index=True)
    check_name: str
    repo_full_name: str = Field(index=True)
    branch: str
    passed: bool
    output: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)


class CheckToggleRecord(SQLModel, table=True):
    """Persistent enabled/disabled state for a check."""

    __tablename__ = "check_toggle"  # type: ignore[assignment]

    check_slug: str = Field(primary_key=True)
    enabled: bool = True


class ActionToggleRecord(SQLModel, table=True):
    """Persistent enabled/disabled state for an action."""

    __tablename__ = "action_toggle"  # type: ignore[assignment]

    action_slug: str = Field(primary_key=True)
    enabled: bool = True


# ---------------------------------------------------------------------------
# Action runs
# ---------------------------------------------------------------------------


class ActionRunRecord(SQLModel, table=True):
    """Metadata for a complete action run."""

    __tablename__ = "action_run"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    action_slug: str = Field(index=True)
    action_name: str
    triggered_by: str  # "manual" | "cron" | "api"
    # queued | running | completed | failed | interrupted (see grimoire.state)
    status: str = RunState.QUEUED.value
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None
    owner_id: str = Field(default="", index=True)
    heartbeat_at: Optional[datetime] = None
    lease_expires_at: Optional[datetime] = None


class ActionRunRepoRecord(SQLModel, table=True):
    """Per-repo result within an action run."""

    __tablename__ = "action_run_repo"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(index=True, foreign_key="action_run.id")
    repo_full_name: str
    branch: str
    passed: bool
    output: str = ""


# ---------------------------------------------------------------------------
# Cached GitHub data
# ---------------------------------------------------------------------------


class CachedRepository(SQLModel, table=True):
    """Cached repository metadata from GitHub."""

    __tablename__ = "cached_repository"  # type: ignore[assignment]

    full_name: str = Field(primary_key=True)
    default_branch: str = "main"
    archived: bool = False
    source: str = "static"
    branches_json: str = "[]"  # JSON-encoded list of observed branches
    open_issues: int = 0
    stale_issues: int = 0
    open_pull_requests: int = 0
    stale_pull_requests: int = 0
    last_commit_at: Optional[datetime] = None
    total_branches: int = 0
    workflow_include_json: str = "[]"  # JSON-encoded glob patterns
    workflow_exclude_json: str = "[]"  # JSON-encoded glob patterns
    fetched_at: datetime = Field(default_factory=_utcnow)


class CachedIssue(SQLModel, table=True):
    """Cached open issue."""

    __tablename__ = "cached_issue"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    repo_full_name: str = Field(index=True)
    title: str
    number: int
    url: str
    author: str = ""
    created_at: datetime
    last_comment_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=_utcnow)


class CachedPullRequest(SQLModel, table=True):
    """Cached open pull request."""

    __tablename__ = "cached_pull_request"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    repo_full_name: str = Field(index=True)
    title: str
    number: int
    url: str
    author: str = ""
    created_at: datetime
    last_push_at: Optional[datetime] = None
    last_comment_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=_utcnow)


class CachedWorkflowStatus(SQLModel, table=True):
    """Cached workflow run status."""

    __tablename__ = "cached_workflow_status"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    repo_full_name: str = Field(index=True)
    workflow_name: str
    branch: str
    status: str  # "success" | "failure" | "pending" | "unknown"
    url: str = ""
    run_url: str = ""
    fetched_at: datetime = Field(default_factory=_utcnow)


class CachedETag(SQLModel, table=True):
    """GitHub API ETag for conditional requests."""

    __tablename__ = "cached_etag"  # type: ignore[assignment]

    endpoint_url: str = Field(primary_key=True)
    etag: str = ""
    last_modified: str = ""


# ---------------------------------------------------------------------------
# Engine & session helpers
# ---------------------------------------------------------------------------


async def get_engine(database_path: str | None = None) -> AsyncEngine:
    """Create an async SQLite engine."""
    db_path = database_path or "grimoire.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    return create_async_engine(url, echo=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session(engine: AsyncEngine) -> AsyncSession:
    """Get a new async session."""
    return AsyncSession(engine)


# Columns added after the initial schema. Existing deployments keep their DB,
# so create_all() cannot add them; apply idempotent ALTERs at startup instead.
_RUN_TABLE_ADDITIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "check_run": (
        ("owner_id", "VARCHAR NOT NULL DEFAULT ''"),
        ("heartbeat_at", "DATETIME"),
        ("lease_expires_at", "DATETIME"),
    ),
    "action_run": (
        ("owner_id", "VARCHAR NOT NULL DEFAULT ''"),
        ("heartbeat_at", "DATETIME"),
        ("lease_expires_at", "DATETIME"),
    ),
}


async def ensure_schema_compatibility(engine: AsyncEngine) -> None:
    """Add columns introduced after an existing database was created.

    Grimoire has no migration tool; this keeps deployed databases working when
    a new column is added without requiring the user to delete grimoire.db.
    """
    async with engine.begin() as conn:
        for table, additions in _RUN_TABLE_ADDITIONS.items():
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in result.fetchall()}
            if not existing:
                continue  # table not created yet
            for column, definition in additions:
                if column not in existing:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    )


async def cleanup_stale_runs(engine: AsyncEngine) -> None:
    """Recover runs left by a previous process without stealing live leases.

    Startup used to mark every queued/running row ``interrupted``. That is
    unsafe with more than one worker: starting worker B would kill worker A's
    in-flight runs. Reclaim only rows whose lease has expired (or is missing).
    """
    await reclaim_expired_runs(engine)


def _lease_deadline(now: datetime) -> datetime:
    return now + timedelta(seconds=RUN_LEASE_SECONDS)


async def transition_run(
    engine: AsyncEngine,
    model: Any,
    run_id: int,
    allowed_from: tuple[str, ...],
    to_state: RunState,
    *,
    owner_id: str | None = None,
) -> bool:
    """Atomically move a run between states; return True if this caller won.

    A compare-and-set update makes terminal states absorbing: a run reclaimed
    to ``interrupted`` cannot be reopened by a late engine write.
    """
    values: dict[str, Any] = {"status": to_state.value}
    if to_state.value in TERMINAL_RUN_STATES:
        values["finished_at"] = _utcnow()
        values["lease_expires_at"] = None

    statement = update(model).where(
        model.id == run_id,
        model.status.in_(allowed_from),
    )
    if owner_id is not None:
        statement = statement.where(model.owner_id == owner_id)
    statement = statement.values(**values)

    async with AsyncSession(engine) as session:
        result = await exec_raw(session, statement)
        await session.commit()
        return bool(result.rowcount)


async def complete_run(
    engine: AsyncEngine, model: Any, run_id: int, *, owner_id: str | None = None
) -> bool:
    """Mark a running run completed only if this caller still owns it."""
    return await transition_run(
        engine,
        model,
        run_id,
        (RunState.RUNNING.value,),
        RunState.COMPLETED,
        owner_id=owner_id,
    )


async def fail_run(
    engine: AsyncEngine, model: Any, run_id: int, *, owner_id: str | None = None
) -> bool:
    """Mark a running run failed only if this caller still owns it."""
    return await transition_run(
        engine,
        model,
        run_id,
        (RunState.RUNNING.value,),
        RunState.FAILED,
        owner_id=owner_id,
    )


async def mark_run_running(engine: AsyncEngine, model: Any, run_id: int) -> bool:
    """Claim a queued run. Returns False when it is no longer queued."""
    now = _utcnow()
    statement = (
        update(model)
        .where(model.id == run_id, model.status == RunState.QUEUED.value)
        .values(
            status=RunState.RUNNING.value,
            owner_id=PROCESS_OWNER_ID,
            heartbeat_at=now,
            lease_expires_at=_lease_deadline(now),
            finished_at=None,
        )
    )
    async with AsyncSession(engine) as session:
        result = await exec_raw(session, statement)
        await session.commit()
        return bool(result.rowcount)


async def heartbeat_run(engine: AsyncEngine, model: Any, run_id: int) -> None:
    """Refresh the lease of a run only if this process still owns it."""
    async with AsyncSession(engine) as session:
        record = await session.get(model, run_id)
        if (
            record is None
            or record.status != RunState.RUNNING.value
            or record.owner_id != PROCESS_OWNER_ID
        ):
            return
        now = _utcnow()
        record.heartbeat_at = now
        record.lease_expires_at = _lease_deadline(now)
        session.add(record)
        await session.commit()


async def _heartbeat_loop(
    engine: AsyncEngine, model: Any, run_id: int, interval: float
) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await heartbeat_run(engine, model, run_id)
        except Exception:  # noqa: BLE001 - heartbeat must not kill the run
            logger.exception("Heartbeat failed for run %s", run_id)


def start_run_heartbeat(
    engine: AsyncEngine, model: Any, run_id: int
) -> asyncio.Task[None]:
    """Start refreshing the run lease in the background."""
    interval = max(1.0, RUN_LEASE_SECONDS / 3)
    return asyncio.create_task(_heartbeat_loop(engine, model, run_id, interval))


async def reclaim_expired_runs(engine: AsyncEngine) -> int:
    """Mark runs whose owner stopped heartbeating as 'interrupted'.

    Startup recovery handles the single-process case; this allows a periodic
    sweep so a crashed owner does not leave a run 'running' forever.
    """
    now = _utcnow()
    cutoff = now - timedelta(seconds=RUN_LEASE_SECONDS)
    reclaimed = 0
    models: tuple[Any, Any] = (CheckRunRecord, ActionRunRecord)
    async with AsyncSession(engine) as session:
        for model in models:
            rows = (
                await session.exec(
                    select(model).where(
                        or_(
                            and_(
                                model.status == RunState.RUNNING.value,
                                or_(
                                    model.lease_expires_at.is_(None),
                                    model.lease_expires_at < now,
                                ),
                            ),
                            and_(
                                model.status == RunState.QUEUED.value,
                                model.started_at < cutoff,
                            ),
                            # A corrupt/unknown status is not terminal and not
                            # reclaimable by the normal predicates; reclaim it
                            # so it cannot strand forever.
                            model.status.notin_(tuple(ALL_RUN_STATES)),
                        )
                    )
                )
            ).all()
            for row in rows:
                row.status = RunState.INTERRUPTED.value
                row.finished_at = now
                row.lease_expires_at = None
            reclaimed += len(rows)
        await session.commit()
    return reclaimed


async def restore_check_toggles(engine: AsyncEngine, checks: Sequence[Any]) -> None:
    """Apply persisted toggle state to in-memory check definitions on startup."""
    async with AsyncSession(engine) as session:
        records = (await session.exec(select(CheckToggleRecord))).all()
        toggle_map = {r.check_slug: r.enabled for r in records}
    for check in checks:
        if check.slug in toggle_map:
            check.enabled = toggle_map[check.slug]


async def restore_action_toggles(engine: AsyncEngine, actions: Sequence[Any]) -> None:
    """Apply persisted toggle state to in-memory action definitions on startup."""
    async with AsyncSession(engine) as session:
        records = (await session.exec(select(ActionToggleRecord))).all()
        toggle_map = {r.action_slug: r.enabled for r in records}
    for action in actions:
        if action.slug in toggle_map:
            action.enabled = toggle_map[action.slug]
