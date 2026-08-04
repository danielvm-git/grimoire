"""MCP tool implementations for Grimoire repository monitoring and checks."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.checks.engine import run_check_for_all_targets
from grimoire.checks.queries import get_check_backlog, get_latest_check_results

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.checks.loader import CheckDefinition
    from grimoire.models import TrackedRepository
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
        """List all loaded check definitions."""
        return [
            {
                "slug": c.slug,
                "name": c.name,
                "description": c.description,
                "severity": c.severity,
            }
            for c in self.checks
        ]

    async def get_repo_checks_status(
        self, repo: str, refresh: bool = False
    ) -> dict[str, Any]:
        """Query overall check passing/failing status for a repository."""
        validate_repo(repo)

        if refresh:
            for check in self.checks:
                await run_check_for_all_targets(
                    check=check,
                    repos=self.repos,
                    workspace=self.workspace,
                    engine=self.engine,
                    triggered_by="api",
                    specific_repo=repo,
                )

        async with AsyncSession(self.engine) as session:
            results = await get_latest_check_results(session, repo_full_name=repo)

        passing_count = sum(1 for r in results if r.passed)
        failing_count = sum(1 for r in results if not r.passed)

        return {
            "repository": repo,
            "overall_status": "passing"
            if failing_count == 0 and len(results) > 0
            else ("failing" if failing_count > 0 else "unknown"),
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

        if refresh:
            for check in self.checks:
                await run_check_for_all_targets(
                    check=check,
                    repos=self.repos,
                    workspace=self.workspace,
                    engine=self.engine,
                    triggered_by="api",
                    specific_repo=repo,
                )

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
        if check_slug:
            validate_check_slug(check_slug)

        target_checks = self.checks
        if check_slug:
            target_checks = [c for c in self.checks if c.slug == check_slug]
            if not target_checks:
                raise ValueError(f"Check with slug '{check_slug}' not found.")

        executed_summary = []
        for check in target_checks:
            results = await run_check_for_all_targets(
                check=check,
                repos=self.repos,
                workspace=self.workspace,
                engine=self.engine,
                triggered_by="api",
                specific_repo=repo,
            )
            executed_summary.append(
                {
                    "check_slug": check.slug,
                    "check_name": check.name,
                    "results_count": len(results),
                    "passed": all(r.passed for r in results) if results else True,
                }
            )

        return {
            "repository": repo,
            "executed_checks_count": len(executed_summary),
            "details": executed_summary,
        }
