"""Check execution engine."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.database import (
    PROCESS_OWNER_ID,
    RUN_LEASE_SECONDS,
    CheckResultRecord,
    CheckRunRecord,
    complete_run,
    fail_run,
    mark_run_running,
    start_run_heartbeat,
    touch_queued_runs,
)
from grimoire.models import CheckResult
from grimoire.observability.metrics import update_check_metrics
from grimoire.script import (
    create_script_process,
    read_stdout_stderr_capped,
    terminate_process,
)
from grimoire.state import RunState
from grimoire.targeting import resolve_targets, target_env

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.checks.loader import CheckDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

OUTPUT_SIZE_CAP = 64 * 1024  # 64 KB
_DEFAULT_TIMEOUT = 300  # 5 minutes
_CONCURRENCY = 5

logger = logging.getLogger(__name__)


@dataclass
class CheckProgress:
    """Tracks execution progress of a running check."""

    completed: int = 0
    total: int = 0
    expires_at: datetime | None = None


class CheckConflictError(Exception):
    """Raised when a check is already queued or running."""


# In-memory tracking of currently-running check slugs and their progress
_running_checks: dict[str, CheckProgress] = {}
_check_locks: dict[str, asyncio.Lock] = {}


def _check_lock(slug: str) -> asyncio.Lock:
    """Return a per-check lock, creating it on first access."""
    if slug not in _check_locks:
        _check_locks[slug] = asyncio.Lock()
    return _check_locks[slug]


def _memory_lease() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=RUN_LEASE_SECONDS)


def is_check_running(slug: str) -> bool:
    """Return True if the check is currently executing.

    Entries carry a lease so a dropped background task cannot block the slug
    forever (bug: check-admission-guard).
    """
    progress = _running_checks.get(slug)
    if progress is None:
        return False
    if progress.expires_at is not None and progress.expires_at < datetime.now(
        timezone.utc
    ):
        _running_checks.pop(slug, None)
        return False
    return True


def try_start_check(slug: str) -> bool:
    """Atomically check and mark a check as running. Returns True if acquired."""
    if is_check_running(slug):
        return False
    _running_checks[slug] = CheckProgress(expires_at=_memory_lease())
    return True


def get_check_progress(slug: str) -> CheckProgress | None:
    """Return the progress tracker for a running check, or None if idle."""
    return _running_checks.get(slug)


def clear_check_running(slug: str) -> None:
    """Drop any in-memory tracking for *slug* (idempotent)."""
    _running_checks.pop(slug, None)


async def create_check_run(
    engine: AsyncEngine, check: CheckDefinition, triggered_by: str
) -> int:
    """Persist a queued check run and return its id."""
    record = CheckRunRecord(
        check_slug=check.slug,
        check_name=check.name,
        triggered_by=triggered_by,
        status=RunState.QUEUED.value,
    )
    async with AsyncSession(engine) as session:
        session.add(record)
        await session.commit()
        await session.refresh(record)
    run_id = record.id
    if run_id is None:
        raise RuntimeError("check run record was not assigned an id")
    return run_id


async def prepare_check_run(
    engine: AsyncEngine, check: CheckDefinition, triggered_by: str
) -> int:
    """Reserve a check slot and persist a queued run; return its id.

    Every entry point (API, web, cron, refresh, MCP) goes through here, so the
    admission guard cannot be bypassed (bug: check-admission-guard).
    """
    async with _check_lock(check.slug):
        if is_check_running(check.slug):
            raise CheckConflictError(f"Check '{check.slug}' is already running")

        async with AsyncSession(engine) as session:
            stmt = select(CheckRunRecord).where(
                col(CheckRunRecord.check_slug) == check.slug,
                col(CheckRunRecord.status).in_(
                    (RunState.QUEUED.value, RunState.RUNNING.value)
                ),
            )
            existing = (await session.exec(stmt)).first()
            if existing is not None:
                raise CheckConflictError(
                    f"Check '{check.slug}' is already running (run ID: {existing.id})"
                )

        run_id = await create_check_run(engine, check, triggered_by)
        _running_checks[check.slug] = CheckProgress(expires_at=_memory_lease())
        return run_id


async def run_check(
    check: CheckDefinition,
    repo: TrackedRepository,
    branch: str,
    workspace: WorkspaceManager,
    engine: AsyncEngine,
    run_id: int | None = None,
) -> CheckResult:
    """Run a single check script against a repo+branch and persist the result."""
    passed = False
    output = ""
    start_time = time.monotonic()

    try:
        workdir = await workspace.reset_workdir(repo.full_name, branch)
    except Exception as exc:
        output = f"Workspace setup failed: {exc}"
        return await _persist_result(
            check, repo, branch, passed, output, engine, run_id
        )

    env = target_env(workspace, repo, branch)

    # Give each check subprocess its own temp/runtime directory to avoid
    # conflicts when tools (e.g. charmcraft) use shared state files.
    tmpdir = tempfile.mkdtemp(prefix="grimoire-check-")
    env["TMPDIR"] = tmpdir
    env["XDG_RUNTIME_DIR"] = tmpdir

    proc: asyncio.subprocess.Process | None = None
    tmp_script = None
    try:
        proc, tmp_script = await create_script_process(
            check.script,
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        # Read both streams with bounded rolling buffers (bug #3) instead of
        # communicate(), which buffers the entire output in RAM. Each stream is
        # capped per-stream to bound memory; the combined output is capped again
        # below to preserve the 64KB user-facing contract.
        stdout_text, stderr_text = await asyncio.wait_for(
            read_stdout_stderr_capped(proc, cap=OUTPUT_SIZE_CAP),
            timeout=_DEFAULT_TIMEOUT,
        )
        stdout_text = stdout_text.rstrip()
        stderr_text = stderr_text.rstrip()
        passed = proc.returncode == 0

        # Build combined output with clear sections
        parts: list[str] = []
        if stdout_text:
            parts.append(stdout_text)
        if stderr_text:
            if stdout_text:
                parts.append("")
            parts.append(f"[stderr]\n{stderr_text}")
        if not passed:
            parts.append(f"\n[exit code {proc.returncode}]")
        output = "\n".join(parts)
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
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Cap the combined output to the last 64KB (preserves user-facing contract).
    if len(output) > OUTPUT_SIZE_CAP:
        output = "[output truncated — showing last 64KB]\n" + output[-OUTPUT_SIZE_CAP:]

    duration = time.monotonic() - start_time
    update_check_metrics(check.slug, repo.full_name, branch, passed, duration)

    return await _persist_result(check, repo, branch, passed, output, engine, run_id)


async def _persist_result(
    check: CheckDefinition,
    repo: TrackedRepository,
    branch: str,
    passed: bool,
    output: str,
    engine: AsyncEngine,
    run_id: int | None = None,
) -> CheckResult:
    """Create a CheckResult, persist it to the database, and return it."""
    now = datetime.now(timezone.utc)
    result = CheckResult(
        check_name=check.name,
        check_slug=check.slug,
        repo_full_name=repo.full_name,
        branch=branch,
        passed=passed,
        output=output,
        timestamp=now,
    )

    record = CheckResultRecord(
        run_id=run_id,
        check_slug=check.slug,
        check_name=check.name,
        repo_full_name=repo.full_name,
        branch=branch,
        passed=passed,
        output=output,
        timestamp=now,
    )
    async with AsyncSession(engine) as session:
        session.add(record)
        await session.commit()

    return result


async def run_check_for_all_targets(
    check: CheckDefinition,
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
    specific_repo: str | None = None,
    triggered_by: str = "manual",
    run_id: int | None = None,
) -> list[CheckResult]:
    """Resolve targets and run the check for every repo × branch combination."""
    if run_id is None:
        run_id = await prepare_check_run(engine, check, triggered_by)
    if not await mark_run_running(engine, CheckRunRecord, run_id):
        logger.warning(
            "Check run %s for '%s' was no longer queued; refusing to execute",
            run_id,
            check.slug,
        )
        return []
    heartbeat = start_run_heartbeat(engine, CheckRunRecord, run_id)

    # Register in-memory tracking (may already be set by try_start_check)
    if check.slug not in _running_checks:
        _running_checks[check.slug] = CheckProgress()
    progress = _running_checks[check.slug]
    try:
        resolved = await resolve_targets(check.targets, repos, workspace)

        if specific_repo is not None:
            resolved = [(r, b) for r, b in resolved if r.full_name == specific_repo]

        # Count total tasks before starting
        task_list: list[tuple[TrackedRepository, str]] = []
        for repo, branches in resolved:
            for branch in branches:
                task_list.append((repo, branch))

        progress.total = len(task_list)

        sem = asyncio.Semaphore(_CONCURRENCY)

        async def _run(repo: TrackedRepository, branch: str) -> CheckResult:
            async with sem:
                result = await run_check(check, repo, branch, workspace, engine, run_id)
                progress.completed += 1
                return result

        tasks: list[asyncio.Task[CheckResult]] = []
        for repo, branch in task_list:
            tasks.append(asyncio.create_task(_run(repo, branch)))

        if not tasks:
            results: list[CheckResult] = []
        else:
            results = list(await asyncio.gather(*tasks))

        # Mark run as completed only if this process still owns a running row.
        if not await complete_run(
            engine, CheckRunRecord, run_id, owner_id=PROCESS_OWNER_ID
        ):
            logger.warning(
                "Check run %s for '%s' was reclaimed before completion; "
                "leaving its terminal status untouched",
                run_id,
                check.slug,
            )

        return results
    except Exception:
        # Mark run as failed so it doesn't leave ghost "running" records.
        if not await fail_run(
            engine, CheckRunRecord, run_id, owner_id=PROCESS_OWNER_ID
        ):
            logger.warning(
                "Check run %s for '%s' was already terminal; not overwriting",
                run_id,
                check.slug,
            )
        raise
    finally:
        heartbeat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat
        _running_checks.pop(check.slug, None)


# ---------------------------------------------------------------------------
# Running every check against a single repository
# ---------------------------------------------------------------------------

# In-memory tracking of repos with a "run all checks" in flight.
_running_repos: dict[str, CheckProgress] = {}


@dataclass
class RepoRunPlan:
    """Checks reserved for a one-repo run, plus those skipped as busy."""

    repo_full_name: str
    reserved: list[tuple[CheckDefinition, int]]
    skipped: list[str]


def is_repo_run_active(repo_full_name: str) -> bool:
    """Return True while a one-repo run for *repo_full_name* is in flight."""
    progress = _running_repos.get(repo_full_name)
    if progress is None:
        return False
    if progress.expires_at is not None and progress.expires_at < datetime.now(
        timezone.utc
    ):
        _running_repos.pop(repo_full_name, None)
        return False
    return True


def get_repo_run_progress(repo_full_name: str) -> CheckProgress | None:
    """Return progress (checks completed/total) for a one-repo run, or None."""
    return _running_repos.get(repo_full_name)


async def reserve_checks_for_repo(
    engine: AsyncEngine,
    checks: list[CheckDefinition],
    repo_full_name: str,
    triggered_by: str = "manual",
) -> RepoRunPlan:
    """Reserve a run slot for every enabled check; skip the ones already busy.

    Raises CheckConflictError if a one-repo run for this repo is in flight.
    """
    if is_repo_run_active(repo_full_name):
        raise CheckConflictError(f"Checks for '{repo_full_name}' are already running")

    reserved: list[tuple[CheckDefinition, int]] = []
    skipped: list[str] = []
    for check in checks:
        if not check.enabled:
            continue
        try:
            run_id = await prepare_check_run(engine, check, triggered_by)
        except CheckConflictError:
            skipped.append(check.slug)
            continue
        reserved.append((check, run_id))

    _running_repos[repo_full_name] = CheckProgress(
        total=len(reserved), expires_at=_memory_lease()
    )
    return RepoRunPlan(repo_full_name, reserved, skipped)


async def run_reserved_checks_for_repo(
    plan: RepoRunPlan,
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
    triggered_by: str = "manual",
) -> list[CheckResult]:
    """Execute the reserved checks for one repo (all its matching branches)."""
    progress = _running_repos.get(plan.repo_full_name) or CheckProgress()
    results: list[CheckResult] = []
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _one(check: CheckDefinition, run_id: int) -> None:
        async with sem:
            try:
                results.extend(
                    await run_check_for_all_targets(
                        check,
                        repos,
                        workspace,
                        engine,
                        specific_repo=plan.repo_full_name,
                        triggered_by=triggered_by,
                        run_id=run_id,
                    )
                )
            except Exception:
                logger.exception(
                    "Check '%s' failed for %s", check.slug, plan.repo_full_name
                )
            finally:
                clear_check_running(check.slug)
                progress.completed += 1

    async def _keep_queued_alive() -> None:
        interval = max(1.0, RUN_LEASE_SECONDS / 3)
        run_ids = [rid for _, rid in plan.reserved]
        while True:
            await asyncio.sleep(interval)
            try:
                await touch_queued_runs(engine, CheckRunRecord, run_ids)
            except Exception:  # noqa: BLE001 - must not kill the batch
                logger.exception("Failed to refresh queued check runs")

    keeper = asyncio.create_task(_keep_queued_alive())
    try:
        await asyncio.gather(*(_one(c, rid) for c, rid in plan.reserved))
    finally:
        keeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keeper
        _running_repos.pop(plan.repo_full_name, None)
    return results
