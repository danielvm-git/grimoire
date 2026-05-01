"""REST API router for checks."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.checks.engine import is_check_running, run_check_for_all_targets
from grimoire.database import CheckToggleRecord

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.checks.loader import CheckDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CheckListItem(BaseModel):
    name: str
    slug: str
    description: str
    schedule: str | None
    enabled: bool
    target_count: int


class CheckResultResponse(BaseModel):
    check_name: str
    check_slug: str
    repo_full_name: str
    branch: str
    passed: bool
    output: str
    timestamp: datetime


class CheckRunResponse(BaseModel):
    check_slug: str
    results: list[CheckResultResponse]


# ---------------------------------------------------------------------------
# Module-level state — set from outside
# ---------------------------------------------------------------------------

_checks: list[CheckDefinition] = []
_repos: list[TrackedRepository] = []
_workspace: WorkspaceManager | None = None
_engine: AsyncEngine | None = None


def set_checks_state(
    checks: list[CheckDefinition],
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
) -> None:
    """Inject dependencies into the checks router."""
    global _checks, _repos, _workspace, _engine  # noqa: PLW0603
    _checks = checks
    _repos = repos
    _workspace = workspace
    _engine = engine


def _find_check(slug: str) -> CheckDefinition:
    for c in _checks:
        if c.slug == slug:
            return c
    raise HTTPException(status_code=404, detail=f"Check '{slug}' not found")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/checks", tags=["checks"])


@router.get("/", response_model=list[CheckListItem])
async def list_checks() -> list[CheckListItem]:
    """List all check definitions with enabled status."""
    items: list[CheckListItem] = []
    for c in _checks:
        items.append(
            CheckListItem(
                name=c.name,
                slug=c.slug,
                description=c.description,
                schedule=c.schedule,
                enabled=c.enabled,
                target_count=0,
            )
        )
    return items


@router.get("/{slug}/results", response_model=list[CheckResultResponse])
async def get_check_results(slug: str) -> list[CheckResultResponse]:
    """Get latest results for a check, grouped by repo+branch."""
    _find_check(slug)
    assert _engine is not None

    query = text(
        "SELECT cr.check_name, cr.check_slug, cr.repo_full_name, cr.branch, "
        "cr.passed, cr.output, cr.timestamp "
        "FROM check_result cr "
        "INNER JOIN ("
        "  SELECT repo_full_name, branch, MAX(timestamp) AS max_ts "
        "  FROM check_result WHERE check_slug = :slug "
        "  GROUP BY repo_full_name, branch"
        ") latest ON cr.repo_full_name = latest.repo_full_name "
        "AND cr.branch = latest.branch "
        "AND cr.timestamp = latest.max_ts "
        "AND cr.check_slug = :slug"
    )

    async with AsyncSession(_engine) as session:
        rows = (await session.exec(query, params={"slug": slug})).all()  # type: ignore[call-arg]

    return [
        CheckResultResponse(
            check_name=row[0],
            check_slug=row[1],
            repo_full_name=row[2],
            branch=row[3],
            passed=bool(row[4]),
            output=row[5],
            timestamp=row[6],
        )
        for row in rows
    ]


@router.post("/{slug}/run", response_model=CheckRunResponse)
async def run_check_endpoint(
    slug: str,
    repo: str | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> CheckRunResponse:
    """Trigger a check run. Optionally filter to a single repo."""
    check = _find_check(slug)
    assert _workspace is not None
    assert _engine is not None

    results = await run_check_for_all_targets(
        check, _repos, _workspace, _engine, specific_repo=repo
    )

    # Update today's history snapshot with latest check metrics
    background_tasks.add_task(_update_snapshot_checks)

    return CheckRunResponse(
        check_slug=slug,
        results=[
            CheckResultResponse(
                check_name=r.check_name,
                check_slug=r.check_slug,
                repo_full_name=r.repo_full_name,
                branch=r.branch,
                passed=r.passed,
                output=r.output,
                timestamp=r.timestamp,
            )
            for r in results
        ],
    )


async def _update_snapshot_checks() -> None:
    """Update today's snapshot with latest check counts."""
    from grimoire.github.service import compute_check_counts, update_snapshot_checks

    assert _engine is not None
    try:
        check_counts = await compute_check_counts(_engine)
        await update_snapshot_checks(_engine, check_counts)
    except Exception:
        logger.exception("Failed to update snapshot check metrics after manual run")


@router.post("/{slug}/toggle")
async def toggle_check(slug: str) -> dict[str, object]:
    """Toggle a check enabled/disabled and persist the state."""
    check = _find_check(slug)
    assert _engine is not None

    check.enabled = not check.enabled

    async with AsyncSession(_engine) as session:
        existing = await session.get(CheckToggleRecord, slug)
        if existing:
            existing.enabled = check.enabled
            session.add(existing)
        else:
            session.add(CheckToggleRecord(check_slug=slug, enabled=check.enabled))
        await session.commit()

    return {"slug": slug, "enabled": check.enabled}


@router.get("/{slug}/status")
async def check_status(slug: str) -> dict[str, object]:
    """Return whether a check is currently running."""
    _find_check(slug)
    return {"slug": slug, "running": is_check_running(slug)}
