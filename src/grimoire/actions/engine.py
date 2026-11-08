"""Action execution engine."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.database import (
    PROCESS_OWNER_ID,
    RUN_LEASE_SECONDS,
    ActionRunRecord,
    ActionRunRepoRecord,
    complete_run,
    fail_run,
    mark_run_running,
    start_run_heartbeat,
)
from grimoire.models import ActionRepoResult, ActionRun
from grimoire.observability.metrics import update_action_metrics
from grimoire.script import create_script_process, read_output_capped, terminate_process
from grimoire.state import RunState
from grimoire.targeting import resolve_targets, target_env

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.actions.loader import ActionDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

OUTPUT_SIZE_CAP = 64 * 1024  # 64 KB
_DEFAULT_TIMEOUT = 600  # 10 minutes

logger = logging.getLogger(__name__)


@dataclass
class ActionProgress:
    """Tracks execution progress of a running action."""

    completed: int = 0
    total: int = 0
    expires_at: datetime | None = None


# In-memory tracking of currently-running action slugs and their progress
_running_actions: dict[str, ActionProgress] = {}
_action_locks: dict[str, asyncio.Lock] = {}


def _memory_lease() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=RUN_LEASE_SECONDS)


def is_action_running(slug: str) -> bool:
    """Return True if the action is currently executing.

    Entries carry a lease so a dropped background task cannot block the slug
    forever (bug: check-admission-guard).
    """
    progress = _running_actions.get(slug)
    if progress is None:
        return False
    if progress.expires_at is not None and progress.expires_at < datetime.now(
        timezone.utc
    ):
        _running_actions.pop(slug, None)
        return False
    return True


def get_action_progress(slug: str) -> ActionProgress | None:
    """Return the progress tracker for a running action, or None if idle."""
    return _running_actions.get(slug)


class ActionConflictError(Exception):
    """Raised when an action is already queued or running."""


def clear_action_running(slug: str) -> None:
    """Drop any in-memory tracking for *slug* (idempotent)."""
    _running_actions.pop(slug, None)


async def prepare_action_run(
    action: ActionDefinition,
    engine: AsyncEngine,
    triggered_by: str,
) -> int:
    """Reserve an action slot and persist a queued run; return its id.

    Raises :class:`ActionConflictError` if the action is already queued or
    running, whether tracked in memory or only in the database.
    """
    async with _action_lock(action.slug):
        if is_action_running(action.slug):
            raise ActionConflictError(f"Action '{action.slug}' is already running")

        async with AsyncSession(engine) as session:
            stmt = select(ActionRunRecord).where(
                col(ActionRunRecord.action_slug) == action.slug,
                col(ActionRunRecord.status).in_(
                    (RunState.QUEUED.value, RunState.RUNNING.value)
                ),
            )
            existing = (await session.exec(stmt)).first()
            if existing is not None:
                raise ActionConflictError(
                    f"Action '{action.slug}' is already running (run ID: {existing.id})"
                )

            record = ActionRunRecord(
                action_slug=action.slug,
                action_name=action.name,
                triggered_by=triggered_by,
                status=RunState.QUEUED.value,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)

        _running_actions[action.slug] = ActionProgress(expires_at=_memory_lease())
        run_id = record.id
        if run_id is None:
            raise RuntimeError("action run record was not assigned an id")
        return run_id


def _action_lock(slug: str) -> asyncio.Lock:
    """Return a per-action lock, creating it on first access."""
    if slug not in _action_locks:
        _action_locks[slug] = asyncio.Lock()
    return _action_locks[slug]


async def run_action(
    action: ActionDefinition,
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
    triggered_by: str,
    specific_repo: str | None = None,
    run_id: int | None = None,
) -> ActionRun:
    """Run an action sequentially against each target repo+branch.

    Raises :class:`ActionConflictError` if the action is already queued/running.
    """
    now = datetime.now(timezone.utc)

    if run_id is None:
        run_id = await prepare_action_run(action, engine, triggered_by)
    if not await mark_run_running(engine, ActionRunRecord, run_id):
        raise RuntimeError(
            f"Action run {run_id} for '{action.slug}' was no longer queued"
        )
    heartbeat = start_run_heartbeat(engine, ActionRunRecord, run_id)

    # 3. Resolve targets and execute
    results: list[ActionRepoResult] = []
    progress = _running_actions.setdefault(action.slug, ActionProgress())

    try:
        if action.targets is None:
            # Global action: run script once, not per-repo
            progress.total = 1
            passed, output = await _execute_global_action(action, workspace)
            result = ActionRepoResult(
                repo_full_name="(global)",
                branch="",
                passed=passed,
                output=output,
            )
            results.append(result)
            progress.completed = 1

            repo_record = ActionRunRepoRecord(
                run_id=run_id,
                repo_full_name="(global)",
                branch="",
                passed=passed,
                output=output,
            )
            async with AsyncSession(engine) as session:
                session.add(repo_record)
                await session.commit()
        else:
            # Per-repo action
            resolved = await resolve_targets(action.targets, repos, workspace)
            if specific_repo is not None:
                resolved = [(r, b) for r, b in resolved if r.full_name == specific_repo]

            # Count total repo×branch tasks
            progress.total = sum(len(branches) for _, branches in resolved)

            for repo, branches in resolved:
                for branch in branches:
                    passed, output = await _execute_action(
                        action, repo, branch, workspace
                    )
                    result = ActionRepoResult(
                        repo_full_name=repo.full_name,
                        branch=branch,
                        passed=passed,
                        output=output,
                    )
                    results.append(result)
                    progress.completed += 1

                    repo_record = ActionRunRepoRecord(
                        run_id=run_id,
                        repo_full_name=repo.full_name,
                        branch=branch,
                        passed=passed,
                        output=output,
                    )
                    async with AsyncSession(engine) as session:
                        session.add(repo_record)
                        await session.commit()

        # Mark run as completed only if this process still owns a running row.
        finished_at = datetime.now(timezone.utc)
        if not await complete_run(
            engine, ActionRunRecord, run_id, owner_id=PROCESS_OWNER_ID
        ):
            logger.warning(
                "Action run %s for '%s' was reclaimed before completion; "
                "leaving its terminal status untouched",
                run_id,
                action.slug,
            )
    except Exception:
        # Mark run as failed so it doesn't permanently block future runs.
        if not await fail_run(
            engine, ActionRunRecord, run_id, owner_id=PROCESS_OWNER_ID
        ):
            logger.warning(
                "Action run %s for '%s' was already terminal; not overwriting",
                run_id,
                action.slug,
            )
        raise
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
        _running_actions.pop(action.slug, None)

    # 6. Return summary
    duration = (finished_at - now).total_seconds()
    update_action_metrics(action.slug, duration)

    return ActionRun(
        action_name=action.name,
        action_slug=action.slug,
        triggered_by=triggered_by,
        started_at=now,
        finished_at=finished_at,
        results=results,
    )


async def _execute_global_action(
    action: ActionDefinition,
    workspace: WorkspaceManager,
) -> tuple[bool, str]:
    """Run the action script once, not tied to any specific repo."""
    cwd = workspace.workspace_dir
    cwd.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **workspace.get_env()}

    passed = False
    output = ""

    proc: asyncio.subprocess.Process | None = None
    tmp_script = None
    try:
        proc, tmp_script = await create_script_process(
            action.script,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        output = await asyncio.wait_for(
            read_output_capped(proc, cap=OUTPUT_SIZE_CAP), timeout=_DEFAULT_TIMEOUT
        )
        passed = proc.returncode == 0
    except asyncio.TimeoutError:
        output = f"Timed out after {_DEFAULT_TIMEOUT}s"
        passed = False
        await terminate_process(proc)
    except OSError as exc:
        output = f"Failed to execute: {exc}"
        passed = False
    finally:
        await terminate_process(proc)
        if tmp_script is not None:
            tmp_script.unlink(missing_ok=True)

    return passed, output


async def _execute_action(
    action: ActionDefinition,
    repo: TrackedRepository,
    branch: str,
    workspace: WorkspaceManager,
) -> tuple[bool, str]:
    """Run the action script in a repo+branch workdir. Returns (passed, output)."""
    # Pre-execution: sync then reset
    await workspace.sync_repo(repo)
    workdir = await workspace.reset_workdir(repo.full_name, branch)
    env = target_env(workspace, repo, branch)

    passed = False
    output = ""

    proc: asyncio.subprocess.Process | None = None
    tmp_script = None
    try:
        proc, tmp_script = await create_script_process(
            action.script,
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        output = await asyncio.wait_for(
            read_output_capped(proc, cap=OUTPUT_SIZE_CAP), timeout=_DEFAULT_TIMEOUT
        )
        passed = proc.returncode == 0
    except asyncio.TimeoutError:
        output = f"Timed out after {_DEFAULT_TIMEOUT}s"
        passed = False
        await terminate_process(proc)
    except OSError as exc:
        output = f"Failed to execute: {exc}"
        passed = False
    finally:
        await terminate_process(proc)
        if tmp_script is not None:
            tmp_script.unlink(missing_ok=True)

    return passed, output
