"""Unified queries for check results and repository check backlog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.database import CheckResultRecord

if TYPE_CHECKING:
    from grimoire.checks.loader import CheckDefinition


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
    """Calculate the backlog of failing or missing checks for a repository."""
    latest_results = await get_latest_check_results(
        session, repo_full_name=repo_full_name
    )
    results_by_slug = {r.check_slug: r for r in latest_results}

    failed_checks = []
    passing_checks = []
    unexecuted_checks = []

    all_defs = check_definitions or []

    for check_def in all_defs:
        slug = check_def.slug
        if slug in results_by_slug:
            res = results_by_slug[slug]
            output_snippet = (res.output or "")[:65536]  # Cap log snippet at 64 KB
            check_data = {
                "slug": slug,
                "name": check_def.name,
                "description": check_def.description,
                "severity": check_def.severity,
                "passed": res.passed,
                "timestamp": res.timestamp.isoformat() if res.timestamp else None,
                "output": output_snippet,
            }
            if res.passed:
                passing_checks.append(check_data)
            else:
                failed_checks.append(check_data)
        else:
            unexecuted_checks.append(
                {
                    "slug": slug,
                    "name": check_def.name,
                    "description": check_def.description,
                    "severity": check_def.severity,
                    "passed": False,
                    "status": "unexecuted",
                }
            )

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
