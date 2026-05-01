"""Action execution engine."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.database import ActionRunRecord, ActionRunRepoRecord
from grimoire.models import ActionRepoResult, ActionRun
from grimoire.script import create_script_process
from grimoire.targeting import resolve_targets

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.actions.loader import ActionDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

OUTPUT_SIZE_CAP = 64 * 1024  # 64 KB
_DEFAULT_TIMEOUT = 600  # 10 minutes


class ActionConflictError(Exception):
    """Raised when an action is already running."""


async def run_action(
    action: ActionDefinition,
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
    triggered_by: str,
    specific_repo: str | None = None,
) -> ActionRun:
    """Run an action sequentially against each target repo+branch.

    Raises :class:`ActionConflictError` if the action is already running.
    """
    now = datetime.now(timezone.utc)

    # 1. Check concurrent run guard
    async with AsyncSession(engine) as session:
        stmt = select(ActionRunRecord).where(
            ActionRunRecord.action_slug == action.slug,
            ActionRunRecord.status == "running",
        )
        existing = (await session.exec(stmt)).first()
        if existing is not None:
            raise ActionConflictError(
                f"Action '{action.slug}' is already running (run ID: {existing.id})"
            )

    # 2. Create run record
    run_record = ActionRunRecord(
        action_slug=action.slug,
        action_name=action.name,
        triggered_by=triggered_by,
        status="running",
        started_at=now,
    )
    async with AsyncSession(engine) as session:
        session.add(run_record)
        await session.commit()
        await session.refresh(run_record)

    run_id: int = run_record.id  # type: ignore[assignment]

    # 3. Resolve targets and execute
    results: list[ActionRepoResult] = []

    if action.targets is None:
        # Global action: run script once, not per-repo
        passed, output = await _execute_global_action(action, workspace)
        result = ActionRepoResult(
            repo_full_name="(global)",
            branch="",
            passed=passed,
            output=output,
        )
        results.append(result)

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
        targets = await resolve_targets(action.targets, repos, workspace)
        if specific_repo is not None:
            targets = [r for r in targets if r.full_name == specific_repo]

        for repo in targets:
            branches = repo.branches or [repo.default_branch]
            for branch in branches:
                passed, output = await _execute_action(action, repo, branch, workspace)
                result = ActionRepoResult(
                    repo_full_name=repo.full_name,
                    branch=branch,
                    passed=passed,
                    output=output,
                )
                results.append(result)

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

    # 5. Update run record
    finished_at = datetime.now(timezone.utc)
    async with AsyncSession(engine) as session:
        record = await session.get(ActionRunRecord, run_id)
        assert record is not None
        record.status = "completed"
        record.finished_at = finished_at
        session.add(record)
        await session.commit()

    # 6. Return summary
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
        stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=_DEFAULT_TIMEOUT)
        output = stdout_bytes.decode(errors="replace")
        passed = proc.returncode == 0
    except asyncio.TimeoutError:
        output = f"Timed out after {_DEFAULT_TIMEOUT}s"
        passed = False
        if proc is not None:
            proc.kill()
            await proc.wait()
    except OSError as exc:
        output = f"Failed to execute: {exc}"
        passed = False
    finally:
        if tmp_script is not None:
            tmp_script.unlink(missing_ok=True)

    # Cap output
    if len(output) > OUTPUT_SIZE_CAP:
        output = "[output truncated — showing last 64KB]\n" + output[-OUTPUT_SIZE_CAP:]

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
    env = {**os.environ, **workspace.get_env()}

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
        stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=_DEFAULT_TIMEOUT)
        output = stdout_bytes.decode(errors="replace")
        passed = proc.returncode == 0
    except asyncio.TimeoutError:
        output = f"Timed out after {_DEFAULT_TIMEOUT}s"
        passed = False
        if proc is not None:
            proc.kill()
            await proc.wait()
    except OSError as exc:
        output = f"Failed to execute: {exc}"
        passed = False
    finally:
        if tmp_script is not None:
            tmp_script.unlink(missing_ok=True)

    # Cap output
    if len(output) > OUTPUT_SIZE_CAP:
        output = "[output truncated — showing last 64KB]\n" + output[-OUTPUT_SIZE_CAP:]

    return passed, output
