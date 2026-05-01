"""REST API router for actions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.actions.engine import ActionConflictError, run_action
from grimoire.database import ActionRunRecord, ActionRunRepoRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.actions.loader import ActionDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ActionListItem(BaseModel):
    name: str
    slug: str
    description: str
    schedule: str | None
    target_count: int


class ActionRunSummary(BaseModel):
    id: int
    action_slug: str
    action_name: str
    triggered_by: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    total_repos: int
    passed_repos: int


class ActionRepoResultResponse(BaseModel):
    repo_full_name: str
    branch: str
    passed: bool
    output: str


class ActionRunDetail(BaseModel):
    id: int
    action_slug: str
    action_name: str
    triggered_by: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    results: list[ActionRepoResultResponse]


# ---------------------------------------------------------------------------
# Module-level state — set from outside
# ---------------------------------------------------------------------------

_actions: list[ActionDefinition] = []
_repos: list[TrackedRepository] = []
_workspace: WorkspaceManager | None = None
_engine: AsyncEngine | None = None


def set_actions_state(
    actions: list[ActionDefinition],
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
) -> None:
    """Inject dependencies into the actions router."""
    global _actions, _repos, _workspace, _engine  # noqa: PLW0603
    _actions = actions
    _repos = repos
    _workspace = workspace
    _engine = engine


def _find_action(slug: str) -> ActionDefinition:
    for a in _actions:
        if a.slug == slug:
            return a
    raise HTTPException(status_code=404, detail=f"Action '{slug}' not found")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("/", response_model=list[ActionListItem])
async def list_actions() -> list[ActionListItem]:
    """List all action definitions."""
    import re

    items: list[ActionListItem] = []
    for a in _actions:
        count = 0
        if a.targets is None:
            count = 0
        elif a.targets.list is not None:
            count = len(a.targets.list)
        elif a.targets.regex is not None:
            pattern = re.compile(a.targets.regex)
            count = sum(1 for r in _repos if pattern.search(r.full_name))
        # script-based targeting: count stays 0 (requires workspace execution)
        items.append(
            ActionListItem(
                name=a.name,
                slug=a.slug,
                description=a.description,
                schedule=a.schedule,
                target_count=count,
            )
        )
    return items


@router.get("/{slug}/runs", response_model=list[ActionRunSummary])
async def list_action_runs(slug: str) -> list[ActionRunSummary]:
    """List run history for an action (reverse chronological)."""
    _find_action(slug)
    assert _engine is not None

    async with AsyncSession(_engine) as session:
        stmt = (
            select(ActionRunRecord)
            .where(ActionRunRecord.action_slug == slug)
            .order_by(ActionRunRecord.started_at.desc())  # type: ignore[union-attr]
        )
        runs = (await session.exec(stmt)).all()

        summaries: list[ActionRunSummary] = []
        for run in runs:
            repo_stmt = select(ActionRunRepoRecord).where(ActionRunRepoRecord.run_id == run.id)
            repo_results = (await session.exec(repo_stmt)).all()
            total = len(repo_results)
            passed = sum(1 for r in repo_results if r.passed)
            summaries.append(
                ActionRunSummary(
                    id=run.id,  # type: ignore[arg-type]
                    action_slug=run.action_slug,
                    action_name=run.action_name,
                    triggered_by=run.triggered_by,
                    status=run.status,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    total_repos=total,
                    passed_repos=passed,
                )
            )

    return summaries


@router.get("/{slug}/runs/{run_id}", response_model=ActionRunDetail)
async def get_action_run(slug: str, run_id: int) -> ActionRunDetail:
    """Get a specific run with per-repo results and logs."""
    _find_action(slug)
    assert _engine is not None

    async with AsyncSession(_engine) as session:
        stmt = select(ActionRunRecord).where(
            ActionRunRecord.id == run_id,
            ActionRunRecord.action_slug == slug,
        )
        run = (await session.exec(stmt)).first()
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        repo_stmt = select(ActionRunRepoRecord).where(ActionRunRepoRecord.run_id == run_id)
        repo_results = (await session.exec(repo_stmt)).all()

    return ActionRunDetail(
        id=run.id,  # type: ignore[arg-type]
        action_slug=run.action_slug,
        action_name=run.action_name,
        triggered_by=run.triggered_by,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        results=[
            ActionRepoResultResponse(
                repo_full_name=r.repo_full_name,
                branch=r.branch,
                passed=r.passed,
                output=r.output,
            )
            for r in repo_results
        ],
    )


@router.post("/{slug}/run", response_model=ActionRunDetail)
async def run_action_endpoint(slug: str, repo: str | None = None) -> ActionRunDetail:
    """Trigger an action. Returns 409 if already running."""
    action = _find_action(slug)
    assert _workspace is not None
    assert _engine is not None

    if action.targets is None and repo is not None:
        raise HTTPException(
            status_code=400,
            detail="repo parameter is not valid for global actions (no targets)",
        )

    try:
        result = await run_action(
            action,
            _repos,
            _workspace,
            _engine,
            triggered_by="manual",
            specific_repo=repo,
        )
    except ActionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Fetch the run record to get the DB id
    async with AsyncSession(_engine) as session:
        stmt = (
            select(ActionRunRecord)
            .where(ActionRunRecord.action_slug == slug)
            .order_by(ActionRunRecord.started_at.desc())  # type: ignore[union-attr]
        )
        run = (await session.exec(stmt)).first()
        assert run is not None

    return ActionRunDetail(
        id=run.id,  # type: ignore[arg-type]
        action_slug=result.action_slug,
        action_name=result.action_name,
        triggered_by=result.triggered_by,
        status=run.status,
        started_at=result.started_at,
        finished_at=result.finished_at,
        results=[
            ActionRepoResultResponse(
                repo_full_name=r.repo_full_name,
                branch=r.branch,
                passed=r.passed,
                output=r.output,
            )
            for r in result.results
        ],
    )
