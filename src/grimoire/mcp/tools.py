"""MCP tool implementations for Grimoire repository monitoring and checks."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.checks.engine import CheckConflictError, run_check_for_all_targets
from grimoire.checks.queries import get_check_backlog, get_latest_check_results

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.checks.loader import CheckDefinition
    from grimoire.models import CheckResult, TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

_REPO_REGEX = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
_CHECK_SLUG_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_repo(repo: str) -> None:
    """Validate repository name format (owner/repo)."""
    if not _REPO_REGEX.match(repo):
        raise ValueError(
            f"Invalid repository format '{repo}'. Expected 'owner/name' (e.g. 'lucabello/grimoire')."
        )


def validate_check_slug(slug: str) -> None:
    """Validate check slug format."""
    if not _CHECK_SLUG_REGEX.match(slug):
        raise ValueError(
            f"Invalid check slug format '{slug}'. Expected alphanumeric characters and hyphens/underscores."
        )


def require_tracked_repo(repo: str, repos: list[TrackedRepository]) -> None:
    """Reject a repository that Grimoire does not track.

    Format validation alone is not enough: ChecksEngine narrows an untracked
    ``specific_repo`` to an empty target list, which used to surface as a
    successful run with zero results.
    """
    if any(candidate.full_name == repo for candidate in repos):
        return

    tracked = ", ".join(sorted(candidate.full_name for candidate in repos)) or "none"
    raise ValueError(
        f"Repository '{repo}' is not tracked by Grimoire. "
        f"Tracked repositories: {tracked}. "
        f"Add it under 'repositories:' in config.yaml, then reload Grimoire."
    )


def _overall_status(passing: int, failing: int) -> str:
    """Summarise per-result counts as passing, failing or unknown."""
    if failing:
        return "failing"
    if passing:
        return "passing"
    return "unknown"


def _execution_detail(
    check: CheckDefinition, results: list[CheckResult], error: str | None
) -> dict[str, Any]:
    """Describe one check execution attempt."""
    return {
        "check_slug": check.slug,
        "check_name": check.name,
        "results_count": len(results),
        "passed": bool(results) and all(r.passed for r in results),
        "error": error,
    }


class MCPToolHandlers:
    """Tool handlers bound to application state."""

    def __init__(
        self,
        engine: AsyncEngine,
        checks: list[CheckDefinition],
        repos: list[TrackedRepository],
        workspace: WorkspaceManager,
    ) -> None:
        self.engine = engine
        self.checks = checks
        self.repos = repos
        self.workspace = workspace

    def _enabled_checks(self) -> list[CheckDefinition]:
        """Checks an operator has not disabled (web, cron and refresh honor this too)."""
        return [check for check in self.checks if check.enabled]

    async def _refresh_checks_for_repo(self, repo: str) -> None:
        """Re-run every check for one repository, tolerating concurrent runs."""
        for check in self._enabled_checks():
            try:
                await run_check_for_all_targets(
                    check=check,
                    repos=self.repos,
                    workspace=self.workspace,
                    engine=self.engine,
                    triggered_by="api",
                    specific_repo=repo,
                )
            except CheckConflictError:
                continue

    async def list_repositories(self) -> list[dict[str, Any]]:
        """List all tracked repositories in Grimoire."""
        return [
            {
                "full_name": repo.full_name,
                "default_branch": repo.default_branch,
                "branches": repo.branches,
                "source": repo.source,
            }
            for repo in self.repos
        ]

    async def list_checks(self) -> list[dict[str, Any]]:
        """List all loaded check definitions, including the scope each one targets."""
        return [
            {
                "slug": c.slug,
                "name": c.name,
                "description": c.description,
                "severity": c.severity,
                "targets": c.targets.model_dump(),
            }
            for c in self.checks
        ]

    async def get_repo_checks_status(
        self, repo: str, refresh: bool = False
    ) -> dict[str, Any]:
        """Query overall check passing/failing status for a repository."""
        validate_repo(repo)
        require_tracked_repo(repo, self.repos)

        if refresh:
            await self._refresh_checks_for_repo(repo)

        async with AsyncSession(self.engine) as session:
            results = await get_latest_check_results(session, repo_full_name=repo)

        passing_count = sum(1 for r in results if r.passed)
        failing_count = sum(1 for r in results if not r.passed)

        return {
            "repository": repo,
            "overall_status": _overall_status(passing_count, failing_count),
            "total_executed_checks": len(results),
            "passing": passing_count,
            "failing": failing_count,
            "latest_results": [
                {
                    "check_slug": r.check_slug,
                    "check_name": r.check_name,
                    "branch": r.branch,
                    "passed": r.passed,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in results
            ],
        }

    async def get_check_backlog_data(
        self, repo: str, refresh: bool = False
    ) -> dict[str, Any]:
        """Get list of failing or unexecuted checks (backlog) for a repository."""
        validate_repo(repo)
        require_tracked_repo(repo, self.repos)

        if refresh:
            await self._refresh_checks_for_repo(repo)

        async with AsyncSession(self.engine) as session:
            return await get_check_backlog(
                session=session,
                repo_full_name=repo,
                check_definitions=self.checks,
            )

    async def run_repo_checks(
        self, repo: str, check_slug: str | None = None
    ) -> dict[str, Any]:
        """Trigger execution of checks for a repository on demand."""
        validate_repo(repo)
        require_tracked_repo(repo, self.repos)

        target_checks = self._enabled_checks()
        if check_slug:
            validate_check_slug(check_slug)
            target_checks = [c for c in target_checks if c.slug == check_slug]
            if not target_checks:
                raise ValueError(
                    f"Check with slug '{check_slug}' not found or disabled."
                )

        details = [await self._execute_check(check, repo) for check in target_checks]
        return {
            "repository": repo,
            "executed_checks_count": len(details),
            "details": details,
        }

    async def _execute_check(self, check: CheckDefinition, repo: str) -> dict[str, Any]:
        """Run one check for one repository and describe the outcome."""
        try:
            results = await run_check_for_all_targets(
                check=check,
                repos=self.repos,
                workspace=self.workspace,
                engine=self.engine,
                triggered_by="api",
                specific_repo=repo,
            )
        except CheckConflictError:
            return _execution_detail(check, [], "already running")

        if results:
            return _execution_detail(check, results, None)

        return _execution_detail(
            check,
            results,
            f"Check '{check.slug}' resolved no targets for '{repo}'. "
            f"Add the repository to the check's targets in data/checks/.",
        )
