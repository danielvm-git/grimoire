"""Web page routes and HTMX partials for the Grimoire dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from grimoire.models import WorkflowStatus

router = APIRouter(tags=["web"])

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ---------------------------------------------------------------------------
# View-model dataclass for template rendering
# ---------------------------------------------------------------------------


@dataclass
class RepoViewModel:
    """Prepared data for rendering a single repo card in the dashboard."""

    full_name: str
    branches: list[str]
    source: str
    open_issues: int
    stale_issues: int
    open_prs: int
    stale_prs: int
    workflow_failures: int
    check_failures: int
    warnings: list[str]
    workflows_by_branch: dict[str, list[WorkflowStatus]]
    checks_by_branch: dict[str, list[dict[str, Any]]]
    fetched_at: datetime | None = None

    @property
    def has_problems(self) -> bool:
        return bool(self.workflow_failures or self.check_failures or self.warnings)

    @property
    def total_workflows(self) -> int:
        return sum(len(wfs) for wfs in self.workflows_by_branch.values())

    @property
    def owner(self) -> str:
        return self.full_name.split("/")[0]

    @property
    def name(self) -> str:
        return self.full_name.split("/", 1)[1]


@dataclass
class DashboardTotals:
    """Aggregate stats for the dashboard stats bar."""

    repos: int = 0
    open_issues: int = 0
    open_prs: int = 0
    stale_issues: int = 0
    stale_prs: int = 0
    workflow_failures: int = 0
    total_workflows: int = 0


@dataclass
class ActionViewModel:
    """Prepared data for rendering an action on the actions page."""

    name: str
    slug: str
    description: str
    schedule: str | None


@dataclass
class ActionRunViewModel:
    """Prepared data for rendering an action run row."""

    id: int
    action_slug: str
    action_name: str
    triggered_by: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    total_repos: int
    passed_repos: int
    results: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

SORT_KEYS: dict[str, Any] = {
    "name": lambda r: r.full_name.lower(),
    "issues": lambda r: r.open_issues,
    "stale_issues": lambda r: r.stale_issues,
    "prs": lambda r: r.open_prs,
    "stale_prs": lambda r: r.stale_prs,
    "workflow_failures": lambda r: r.workflow_failures,
    "check_failures": lambda r: r.check_failures,
}

SORT_LABELS: dict[str, str] = {
    "name": "Name",
    "issues": "Open Issues",
    "stale_issues": "Stale Issues",
    "prs": "Open PRs",
    "stale_prs": "Stale PRs",
    "workflow_failures": "Failing Workflows",
    "check_failures": "Failing Checks",
}


def _sort_repos(repos: list[RepoViewModel], sort: str, direction: str) -> list[RepoViewModel]:
    key_fn = SORT_KEYS.get(sort, SORT_KEYS["name"])
    return sorted(repos, key=key_fn, reverse=(direction == "desc"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _time_ago(dt: datetime) -> str:
    """Return a human-readable 'X ago' string."""
    now = datetime.now(tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _compute_totals(repos: list[RepoViewModel]) -> DashboardTotals:
    totals = DashboardTotals(repos=len(repos))
    for r in repos:
        totals.open_issues += r.open_issues
        totals.open_prs += r.open_prs
        totals.stale_issues += r.stale_issues
        totals.stale_prs += r.stale_prs
        totals.workflow_failures += r.workflow_failures
        totals.total_workflows += r.total_workflows
    return totals


def _build_repo_viewmodels() -> list[RepoViewModel]:
    """Build view models from the in-memory GitHub cache + checks state."""
    from grimoire.checks.router import _checks
    from grimoire.github.router import _cache, _repos

    viewmodels: list[RepoViewModel] = []
    for full_name, stats in _cache.items():
        repo = _repos.get(full_name)
        if repo is None:
            continue

        branches = repo.branches or [stats.default_branch]

        # Group workflows by branch
        workflows_by_branch: dict[str, list[WorkflowStatus]] = {}
        for wf in stats.workflows:
            workflows_by_branch.setdefault(wf.branch, []).append(wf)

        # Count workflow failures
        workflow_failures = sum(1 for w in stats.workflows if w.status == "failure")

        # Build check results from the in-memory check definitions
        checks_by_branch: dict[str, list[dict[str, Any]]] = {}
        check_failures = 0
        for check_def in _checks:
            # Check definitions don't carry latest results directly;
            # the DB holds results. For the dashboard, we skip DB queries
            # and show checks only if we have cached data.
            pass

        viewmodels.append(
            RepoViewModel(
                full_name=full_name,
                branches=branches,
                source=repo.source,
                open_issues=stats.open_issues,
                stale_issues=stats.stale_issues,
                open_prs=stats.open_pull_requests,
                stale_prs=stats.stale_pull_requests,
                workflow_failures=workflow_failures,
                check_failures=check_failures,
                warnings=stats.warnings,
                workflows_by_branch=workflows_by_branch,
                checks_by_branch=checks_by_branch,
                fetched_at=stats.fetched_at,
            )
        )
    return viewmodels


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, sort: str = "name", dir: str = "asc") -> HTMLResponse:
    """Dashboard page — lists all tracked repositories."""
    from grimoire.github.router import _last_refresh

    repos = _build_repo_viewmodels()
    repos = _sort_repos(repos, sort, dir)
    totals = _compute_totals(repos)

    # Collect global warnings
    warnings: list[str] = []
    for r in repos:
        for w in r.warnings:
            if w not in warnings:
                warnings.append(w)

    last_refresh_ago = _time_ago(_last_refresh) if _last_refresh else None

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "repos": repos,
            "totals": totals,
            "warnings": warnings,
            "last_refresh": _last_refresh,
            "last_refresh_ago": last_refresh_ago,
            "sort": sort,
            "dir": dir,
            "sort_labels": SORT_LABELS,
        },
    )


@router.get("/repo/{owner}/{name}", response_class=HTMLResponse)
async def repository_detail(request: Request, owner: str, name: str) -> HTMLResponse:
    """Repository detail page."""
    from grimoire.github.router import _cache, _repos

    full_name = f"{owner}/{name}"
    stats = _cache.get(full_name)
    repo = _repos.get(full_name)

    if stats is None or repo is None:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            context={"entity": f"Repository {full_name}"},
            status_code=404,
        )

    branches = repo.branches or [stats.default_branch]

    workflows_by_branch: dict[str, list[WorkflowStatus]] = {}
    for wf in stats.workflows:
        workflows_by_branch.setdefault(wf.branch, []).append(wf)

    workflow_failures = sum(1 for w in stats.workflows if w.status == "failure")

    checks_by_branch: dict[str, list[dict[str, Any]]] = {}

    return templates.TemplateResponse(
        request,
        "repository.html",
        context={
            "repo_name": full_name,
            "stats": stats,
            "repo": repo,
            "branches": branches,
            "workflows_by_branch": workflows_by_branch,
            "checks_by_branch": checks_by_branch,
            "workflow_failures": workflow_failures,
        },
    )


@router.get("/actions", response_class=HTMLResponse)
async def actions_page(request: Request) -> HTMLResponse:
    """Actions page — list available actions and run history."""
    from grimoire.actions.router import _actions

    action_vms = [
        ActionViewModel(
            name=a.name,
            slug=a.slug,
            description=a.description,
            schedule=a.schedule,
        )
        for a in _actions
    ]

    return templates.TemplateResponse(
        request,
        "actions.html",
        context={
            "actions": action_vms,
            "runs": [],
        },
    )


# ---------------------------------------------------------------------------
# HTMX Partial Routes
# ---------------------------------------------------------------------------


@router.get("/partials/dashboard-cards", response_class=HTMLResponse)
async def dashboard_cards_partial(
    request: Request, sort: str = "name", dir: str = "asc"
) -> HTMLResponse:
    """Return the repo cards grid for HTMX swap."""
    repos = _build_repo_viewmodels()
    repos = _sort_repos(repos, sort, dir)
    return templates.TemplateResponse(
        request,
        "partials/dashboard_cards.html",
        context={
            "repos": repos,
        },
    )


@router.get("/partials/action-run/{run_id}", response_class=HTMLResponse)
async def action_run_partial(request: Request, run_id: int) -> HTMLResponse:
    """Return expanded action run details for inline expansion."""
    return templates.TemplateResponse(
        request,
        "partials/action_run_detail.html",
        context={
            "run_id": run_id,
            "results": [],
        },
    )


@router.get("/partials/check-output/{result_id}", response_class=HTMLResponse)
async def check_output_partial(request: Request, result_id: int) -> HTMLResponse:
    """Return expanded check output."""
    return templates.TemplateResponse(
        request,
        "partials/check_output.html",
        context={
            "result_id": result_id,
            "output": "",
        },
    )
