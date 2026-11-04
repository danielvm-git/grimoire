"""SQLModel table definitions and database engine setup."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.state import RECLAIMABLE_RUN_STATES, RunState

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


async def cleanup_stale_runs(engine: AsyncEngine) -> None:
    """Mark non-terminal runs left by a previous process as 'interrupted'.

    Called at startup — if the app was restarted while runs were queued or
    running, the in-memory tracking is gone and the DB rows would be stuck.
    """
    now = _utcnow()
    models: tuple[Any, Any] = (CheckRunRecord, ActionRunRecord)
    async with AsyncSession(engine) as session:
        for model in models:
            rows = (
                await session.exec(
                    select(model).where(model.status.in_(RECLAIMABLE_RUN_STATES))
                )
            ).all()
            for row in rows:
                row.status = RunState.INTERRUPTED.value
                row.finished_at = now
                row.lease_expires_at = None
        await session.commit()


def _lease_deadline(now: datetime) -> datetime:
    return now + timedelta(seconds=RUN_LEASE_SECONDS)


async def mark_run_running(engine: AsyncEngine, model: Any, run_id: int) -> None:
    """Transition a queued run to 'running' and claim its lease."""
    async with AsyncSession(engine) as session:
        record = await session.get(model, run_id)
        if record is None:
            return
        now = _utcnow()
        record.status = RunState.RUNNING.value
        record.owner_id = PROCESS_OWNER_ID
        record.heartbeat_at = now
        record.lease_expires_at = _lease_deadline(now)
        session.add(record)
        await session.commit()


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
