"""Web page routes and HTMX partials for the Grimoire dashboard."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.config import StalenessConfig
from grimoire.models import WorkflowStatus
from grimoire.targeting import TargetSpec

router = APIRouter(tags=["web"])

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Module-level staleness config — set from app lifespan
_staleness_config: StalenessConfig = StalenessConfig()


def set_staleness_config(config: StalenessConfig) -> None:
    """Register the staleness thresholds from the app config."""
    global _staleness_config  # noqa: PLW0603
    _staleness_config = config


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
    check_warnings: int
    warnings: list[str]
    workflows_by_branch: dict[str, list[WorkflowStatus]]
    checks_by_branch: dict[str, list[dict[str, Any]]]
    fetched_at: datetime | None = None
    last_commit_at: datetime | None = None
    total_branches: int = 0
    stale_branches: int = 0

    @property
    def has_problems(self) -> bool:
        return bool(self.workflow_failures or self.check_failures or self.warnings)

    @property
    def health_status(self) -> str:
        """Three-tier health: 'error', 'warning', or 'ok'.

        Only error-severity check failures affect health.
        Warning-severity failures are reported but do not influence status.
        """
        if self.workflow_failures or self.check_failures:
            return "error"
        if self.stale_issues or self.stale_prs:
            return "warning"
        return "ok"

    @property
    def total_workflows(self) -> int:
        return sum(len(wfs) for wfs in self.workflows_by_branch.values())

    @property
    def total_checks(self) -> int:
        return sum(len(chks) for chks in self.checks_by_branch.values())

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
    repos_ok: int = 0
    repos_warning: int = 0
    repos_error: int = 0
    open_issues: int = 0
    open_prs: int = 0
    stale_issues: int = 0
    stale_prs: int = 0
    workflow_failures: int = 0
    total_workflows: int = 0
    check_failures: int = 0
    check_warnings: int = 0
    total_checks: int = 0


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


@dataclass
class CheckViewModel:
    """Prepared data for rendering a check definition on the checks page."""

    name: str
    slug: str
    description: str
    schedule: str | None
    enabled: bool
    target_summary: str
    script: str
    severity: str = "error"
    pass_count: int = 0
    fail_count: int = 0
    last_run: datetime | str | None = None


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

SORT_KEYS: dict[str, Any] = {
    "name": lambda r: r.full_name.lower(),
    "health": lambda r: {"error": 0, "warning": 1, "ok": 2}.get(r.health_status, 2),
    "issues": lambda r: r.open_issues,
    "stale_issues": lambda r: r.stale_issues,
    "prs": lambda r: r.open_prs,
    "stale_prs": lambda r: r.stale_prs,
    "workflow_failures": lambda r: r.workflow_failures,
    "check_failures": lambda r: r.check_failures,
    "last_activity": lambda r: r.last_commit_at or datetime.min.replace(tzinfo=timezone.utc),
}

SORT_LABELS: dict[str, str] = {
    "name": "Name",
    "health": "Health",
    "issues": "Open Issues",
    "stale_issues": "Stale Issues",
    "prs": "Open PRs",
    "stale_prs": "Stale PRs",
    "workflow_failures": "Failing Workflows",
    "check_failures": "Failing Checks",
    "last_activity": "Last Activity",
}


def _sort_repos(repos: list[RepoViewModel], sort: str, direction: str) -> list[RepoViewModel]:
    key_fn = SORT_KEYS.get(sort, SORT_KEYS["name"])
    return sorted(repos, key=key_fn, reverse=(direction == "desc"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _time_ago(dt: datetime | str) -> str:
    """Return a human-readable 'X ago' string."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
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
        # Health distribution
        status = r.health_status
        if status == "error":
            totals.repos_error += 1
        elif status == "warning":
            totals.repos_warning += 1
        else:
            totals.repos_ok += 1
        totals.open_issues += r.open_issues
        totals.open_prs += r.open_prs
        totals.stale_issues += r.stale_issues
        totals.stale_prs += r.stale_prs
        totals.workflow_failures += r.workflow_failures
        totals.total_workflows += r.total_workflows
        totals.check_failures += r.check_failures
        totals.check_warnings += r.check_warnings
        totals.total_checks += r.total_checks
    return totals


def _resolve_targets_sync(targets: TargetSpec, repo_names: list[str]) -> set[str]:
    """Resolve list/regex targeting without async workspace access.

    Script-based targeting is skipped; those checks appear once they've run.
    """
    if targets.list is not None:
        return set(targets.list) & set(repo_names)
    if targets.regex is not None:
        pattern = re.compile(targets.regex)
        return {name for name in repo_names if pattern.search(name)}
    return set()


_LATEST_RESULTS_SQL = text(
    "SELECT cr.id, cr.check_name, cr.check_slug, cr.repo_full_name, cr.branch, "
    "cr.passed, cr.timestamp "
    "FROM check_result cr "
    "INNER JOIN ("
    "  SELECT check_slug, repo_full_name, branch, MAX(timestamp) AS max_ts "
    "  FROM check_result "
    "  GROUP BY check_slug, repo_full_name, branch"
    ") latest ON cr.check_slug = latest.check_slug "
    "AND cr.repo_full_name = latest.repo_full_name "
    "AND cr.branch = latest.branch "
    "AND cr.timestamp = latest.max_ts"
)


async def _load_check_context(
    repo_names: list[str],
) -> tuple[dict[str, set[str]], dict[tuple[str, str, str], dict[str, Any]]]:
    """Load check targeting and latest DB results.

    Returns (check_targets, results_by_key) where:
    - check_targets: check_slug → set of applicable repo full_names
    - results_by_key: (check_slug, repo_full_name, branch) → result dict
    """
    from grimoire.checks.router import _checks
    from grimoire.checks.router import _engine as _checks_engine

    check_targets: dict[str, set[str]] = {}
    for check_def in _checks:
        if not check_def.enabled:
            continue
        check_targets[check_def.slug] = _resolve_targets_sync(check_def.targets, repo_names)

    results_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    if _checks_engine is not None and _checks:
        async with AsyncSession(_checks_engine) as session:
            result = await session.execute(_LATEST_RESULTS_SQL)
            rows = result.all()
        for row in rows:
            key = (row[2], row[3], row[4])  # check_slug, repo_full_name, branch
            results_by_key[key] = {
                "id": row[0],
                "check_name": row[1],
                "check_slug": row[2],
                "passed": bool(row[5]),
                "timestamp": row[6],
            }

    return check_targets, results_by_key


def _build_checks_for_repo(
    full_name: str,
    branches: list[str],
    check_targets: dict[str, set[str]],
    results_by_key: dict[tuple[str, str, str], dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    """Build checks_by_branch and count failures/warnings for a single repo.

    Returns (checks_by_branch, check_failures, check_warnings) where
    check_failures counts error-severity failures and check_warnings counts
    warning-severity failures.
    """
    from grimoire.checks.router import _checks

    checks_by_branch: dict[str, list[dict[str, Any]]] = {}
    check_failures = 0
    check_warnings = 0
    for check_def in _checks:
        if not check_def.enabled:
            continue
        applies = full_name in check_targets.get(check_def.slug, set())
        for branch in branches:
            key = (check_def.slug, full_name, branch)
            result = results_by_key.get(key)
            if result:
                entry = {
                    "check_name": check_def.name,
                    "check_slug": check_def.slug,
                    "passed": result["passed"],
                    "status": "pass" if result["passed"] else "fail",
                    "severity": check_def.severity,
                    "id": result["id"],
                    "timestamp": result["timestamp"],
                }
                if not result["passed"]:
                    if check_def.severity == "error":
                        check_failures += 1
                    else:
                        check_warnings += 1
            elif applies:
                entry = {
                    "check_name": check_def.name,
                    "check_slug": check_def.slug,
                    "passed": None,
                    "status": "not-run",
                    "severity": check_def.severity,
                    "id": None,
                    "timestamp": None,
                }
            else:
                continue
            checks_by_branch.setdefault(branch, []).append(entry)
    return checks_by_branch, check_failures, check_warnings


async def _build_repo_viewmodels() -> list[RepoViewModel]:
    """Build view models from the in-memory GitHub cache + checks state."""
    from grimoire.github.router import _cache, _repos

    repo_names = list(_cache.keys())
    check_targets, results_by_key = await _load_check_context(repo_names)

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

        # Build check results
        checks_by_branch, check_failures, check_warnings = _build_checks_for_repo(
            full_name, branches, check_targets, results_by_key
        )

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
                check_warnings=check_warnings,
                warnings=stats.warnings,
                workflows_by_branch=workflows_by_branch,
                checks_by_branch=checks_by_branch,
                fetched_at=stats.fetched_at,
                last_commit_at=stats.last_commit_at,
                total_branches=stats.total_branches,
                stale_branches=stats.stale_branches,
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

    repos = await _build_repo_viewmodels()
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
            "staleness": _staleness_config,
            "time_ago": _time_ago,
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

    check_targets, results_by_key = await _load_check_context([full_name])
    checks_by_branch, check_failures, check_warnings = _build_checks_for_repo(
        full_name, branches, check_targets, results_by_key
    )

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
            "check_failures": check_failures,
            "staleness": _staleness_config,
            "time_ago": _time_ago,
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


@router.get("/checks", response_class=HTMLResponse)
async def checks_page(request: Request) -> HTMLResponse:
    """Checks page — list defined checks, toggle, run, view results."""
    from grimoire.checks.router import _checks
    from grimoire.checks.router import _engine as _checks_engine

    # Build per-check aggregate stats from DB
    check_stats: dict[str, dict[str, Any]] = {}
    if _checks_engine is not None and _checks:
        async with AsyncSession(_checks_engine) as session:
            result = await session.execute(_LATEST_RESULTS_SQL)
            rows = result.all()
        for row in rows:
            slug = row[2]
            passed = bool(row[5])
            ts = row[6]
            stats = check_stats.setdefault(slug, {"pass": 0, "fail": 0, "last_run": None})
            if passed:
                stats["pass"] += 1
            else:
                stats["fail"] += 1
            if stats["last_run"] is None or (ts is not None and ts > stats["last_run"]):
                stats["last_run"] = ts

    check_vms = []
    for c in _checks:
        targets = c.targets
        if targets.regex is not None:
            target_summary = f"regex: {targets.regex}"
        elif targets.list is not None:
            target_summary = f"list: {len(targets.list)} repos"
        else:
            target_summary = "script"

        stats = check_stats.get(c.slug, {})
        check_vms.append(
            CheckViewModel(
                name=c.name,
                slug=c.slug,
                description=c.description,
                schedule=c.schedule,
                enabled=c.enabled,
                target_summary=target_summary,
                script=c.script,
                severity=c.severity,
                pass_count=stats.get("pass", 0),
                fail_count=stats.get("fail", 0),
                last_run=stats.get("last_run"),
            )
        )

    # Build results list for the table
    results_list: list[dict[str, Any]] = []
    if _checks_engine is not None and _checks:
        async with AsyncSession(_checks_engine) as session:
            result = await session.execute(
                text(
                    "SELECT cr.id, cr.check_name, cr.check_slug, cr.repo_full_name, "
                    "cr.branch, cr.passed, cr.timestamp "
                    "FROM check_result cr "
                    "INNER JOIN ("
                    "  SELECT check_slug, repo_full_name, branch, MAX(timestamp) AS max_ts "
                    "  FROM check_result "
                    "  GROUP BY check_slug, repo_full_name, branch"
                    ") latest ON cr.check_slug = latest.check_slug "
                    "AND cr.repo_full_name = latest.repo_full_name "
                    "AND cr.branch = latest.branch "
                    "AND cr.timestamp = latest.max_ts "
                    "ORDER BY cr.timestamp DESC"
                )
            )
            rows = result.all()
        for row in rows:
            results_list.append(
                {
                    "id": row[0],
                    "check_name": row[1],
                    "check_slug": row[2],
                    "repo_full_name": row[3],
                    "branch": row[4],
                    "passed": bool(row[5]),
                    "timestamp": row[6],
                }
            )

    return templates.TemplateResponse(
        request,
        "checks.html",
        context={
            "checks": check_vms,
            "results": results_list,
            "time_ago": _time_ago,
        },
    )


# ---------------------------------------------------------------------------
# HTMX Partial Routes
# ---------------------------------------------------------------------------


async def _build_sorted_repos(sort: str, direction: str) -> list[RepoViewModel]:
    """Build and sort repo view models (shared by all dashboard partials)."""
    repos = await _build_repo_viewmodels()
    return _sort_repos(repos, sort, direction)


@router.get("/partials/dashboard-matrix", response_class=HTMLResponse)
async def dashboard_matrix_partial(
    request: Request, sort: str = "name", dir: str = "asc"
) -> HTMLResponse:
    """Return the compact matrix view for HTMX swap."""
    repos = await _build_sorted_repos(sort, dir)
    return templates.TemplateResponse(
        request,
        "partials/dashboard_matrix.html",
        context={
            "repos": repos,
            "sort": sort,
            "dir": dir,
            "staleness": _staleness_config,
            "time_ago": _time_ago,
        },
    )


@router.get("/partials/dashboard-list", response_class=HTMLResponse)
async def dashboard_list_partial(
    request: Request, sort: str = "name", dir: str = "asc"
) -> HTMLResponse:
    """Return the compact list view for HTMX swap."""
    repos = await _build_sorted_repos(sort, dir)
    return templates.TemplateResponse(
        request,
        "partials/dashboard_list.html",
        context={
            "repos": repos,
            "staleness": _staleness_config,
            "time_ago": _time_ago,
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
    from grimoire.checks.router import _engine as _checks_engine

    output = ""
    if _checks_engine is not None:
        async with AsyncSession(_checks_engine) as session:
            result = await session.execute(
                text("SELECT output FROM check_result WHERE id = :id"),
                params={"id": result_id},
            )
            row = result.first()
            if row:
                output = row[0]

    return templates.TemplateResponse(
        request,
        "partials/check_output.html",
        context={
            "result_id": result_id,
            "output": output,
        },
    )


@router.get("/partials/check-results/{slug}", response_class=HTMLResponse)
async def check_results_partial(request: Request, slug: str) -> HTMLResponse:
    """Return per-check latest results table for inline expansion."""
    from grimoire.checks.router import _engine as _checks_engine

    results_list: list[dict[str, Any]] = []
    if _checks_engine is not None:
        query = text(
            "SELECT cr.id, cr.check_name, cr.check_slug, cr.repo_full_name, "
            "cr.branch, cr.passed, cr.timestamp "
            "FROM check_result cr "
            "INNER JOIN ("
            "  SELECT repo_full_name, branch, MAX(timestamp) AS max_ts "
            "  FROM check_result WHERE check_slug = :slug "
            "  GROUP BY repo_full_name, branch"
            ") latest ON cr.repo_full_name = latest.repo_full_name "
            "AND cr.branch = latest.branch "
            "AND cr.timestamp = latest.max_ts "
            "AND cr.check_slug = :slug "
            "ORDER BY cr.timestamp DESC"
        )
        async with AsyncSession(_checks_engine) as session:
            result = await session.execute(query, params={"slug": slug})
            rows = result.all()
        for row in rows:
            results_list.append(
                {
                    "id": row[0],
                    "check_name": row[1],
                    "check_slug": row[2],
                    "repo_full_name": row[3],
                    "branch": row[4],
                    "passed": bool(row[5]),
                    "timestamp": row[6],
                }
            )

    return templates.TemplateResponse(
        request,
        "partials/check_results.html",
        context={
            "results": results_list,
            "time_ago": _time_ago,
        },
    )
