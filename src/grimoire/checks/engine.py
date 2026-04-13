"""Check execution engine."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.database import CheckResultRecord
from grimoire.models import CheckResult
from grimoire.targeting import resolve_targets

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.checks.loader import CheckDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

OUTPUT_SIZE_CAP = 64 * 1024  # 64 KB
_DEFAULT_TIMEOUT = 300  # 5 minutes
_CONCURRENCY = 5


async def run_check(
    check: CheckDefinition,
    repo: TrackedRepository,
    branch: str,
    workspace: WorkspaceManager,
    engine: AsyncEngine,
) -> CheckResult:
    """Run a single check script against a repo+branch and persist the result."""
    workdir = await workspace.reset_workdir(repo.full_name, branch)
    env = {**os.environ, **workspace.get_env()}

    passed = False
    output = ""

    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_shell(
            check.script,
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

    # Cap output
    if len(output) > OUTPUT_SIZE_CAP:
        output = "[output truncated — showing last 64KB]\n" + output[-OUTPUT_SIZE_CAP:]

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

    # Persist to database
    record = CheckResultRecord(
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
) -> list[CheckResult]:
    """Resolve targets and run the check for every repo × branch combination."""
    targets = await resolve_targets(check.targets, repos, workspace)

    if specific_repo is not None:
        targets = [r for r in targets if r.full_name == specific_repo]

    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _run(repo: TrackedRepository, branch: str) -> CheckResult:
        async with sem:
            return await run_check(check, repo, branch, workspace, engine)

    tasks: list[asyncio.Task[CheckResult]] = []
    for repo in targets:
        branches = repo.branches or [repo.default_branch]
        for branch in branches:
            tasks.append(asyncio.create_task(_run(repo, branch)))

    if not tasks:
        return []

    return list(await asyncio.gather(*tasks))
