"""Unified queries for check results and repository check backlog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.database import CheckResultRecord

if TYPE_CHECKING:
    from grimoire.checks.loader import CheckDefinition

MAX_OUTPUT_CHARS = 65536
"""Cap on check output embedded in a backlog entry (64 KiB)."""


def _backlog_entry(
    check_def: CheckDefinition, result: CheckResultRecord | None
) -> dict[str, Any]:
    """Build one backlog entry, keeping the branch the result belongs to."""
    entry: dict[str, Any] = {
        "slug": check_def.slug,
        "name": check_def.name,
        "description": check_def.description,
        "severity": check_def.severity,
    }
    if result is None:
        entry.update({"branch": None, "passed": False, "status": "unexecuted"})
        return entry

    entry.update(
        {
            "branch": result.branch,
            "passed": result.passed,
            "timestamp": result.timestamp.isoformat() if result.timestamp else None,
            "output": (result.output or "")[:MAX_OUTPUT_CHARS],
        }
    )
    return entry


async def get_latest_check_results(
    session: AsyncSession, repo_full_name: str | None = None
) -> list[CheckResultRecord]:
    """Retrieve the latest result record for each (check_slug, repo_full_name, branch)."""
    # Subquery for max timestamp per combination
    subq = select(
        CheckResultRecord.check_slug,
        CheckResultRecord.repo_full_name,
        CheckResultRecord.branch,
        func.max(CheckResultRecord.timestamp).label("max_ts"),
    ).group_by(
        CheckResultRecord.check_slug,
        CheckResultRecord.repo_full_name,
        CheckResultRecord.branch,
    )

    if repo_full_name:
        subq = subq.where(CheckResultRecord.repo_full_name == repo_full_name)

    subq_alias = subq.subquery()

    join_condition = and_(
        CheckResultRecord.check_slug == subq_alias.c.check_slug,  # type: ignore[arg-type]
        CheckResultRecord.repo_full_name == subq_alias.c.repo_full_name,  # type: ignore[arg-type]
        CheckResultRecord.branch == subq_alias.c.branch,  # type: ignore[arg-type]
        CheckResultRecord.timestamp == subq_alias.c.max_ts,  # type: ignore[arg-type]
    )

    query = select(CheckResultRecord).join(subq_alias, join_condition)

    if repo_full_name:
        query = query.where(CheckResultRecord.repo_full_name == repo_full_name)

    exec_res = await session.exec(query)
    return list(exec_res.all())


async def get_check_backlog(
    session: AsyncSession,
    repo_full_name: str,
    check_definitions: list[CheckDefinition] | None = None,
) -> dict[str, Any]:
    """Calculate the backlog of failing or missing checks for a repository.

    Results stay separated per (check, branch) because checks run on every tracked
    branch. Collapsing them by slug alone would let a passing branch mask a failing one.

    Example:
        >>> backlog = await get_check_backlog(session, "acme/api", checks)
        >>> backlog["all_passed"]
        False
    """
    latest_results = await get_latest_check_results(
        session, repo_full_name=repo_full_name
    )
    results_by_slug: dict[str, list[CheckResultRecord]] = {}
    for result in latest_results:
        results_by_slug.setdefault(result.check_slug, []).append(result)

    failed_checks: list[dict[str, Any]] = []
    passing_checks: list[dict[str, Any]] = []
    unexecuted_checks: list[dict[str, Any]] = []

    all_defs = check_definitions or []

    for check_def in all_defs:
        branch_results = sorted(
            results_by_slug.get(check_def.slug, []), key=lambda r: r.branch
        )
        if not branch_results:
            unexecuted_checks.append(_backlog_entry(check_def, None))
            continue

        for result in branch_results:
            entry = _backlog_entry(check_def, result)
            (passing_checks if result.passed else failed_checks).append(entry)

    all_passed = len(failed_checks) == 0 and len(unexecuted_checks) == 0

    return {
        "repository": repo_full_name,
        "all_passed": all_passed,
        "summary": {
            "total_checks": len(all_defs),
            "passing": len(passing_checks),
            "failing": len(failed_checks),
            "unexecuted": len(unexecuted_checks),
        },
        "failing_checks": failed_checks,
        "unexecuted_checks": unexecuted_checks,
        "passing_checks": passing_checks,
    }
