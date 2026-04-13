"""Prometheus metrics for Grimoire."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from grimoire.models import RepositoryStats

# ---------------------------------------------------------------------------
# Repository health gauges
# ---------------------------------------------------------------------------

REPOS_TOTAL = Gauge("grimoire_repositories_total", "Number of tracked repos")
OPEN_ISSUES = Gauge("grimoire_open_issues_total", "Open issues", ["repo"])
STALE_ISSUES = Gauge("grimoire_stale_issues_total", "Stale issues", ["repo"])
OPEN_PRS = Gauge("grimoire_open_pull_requests_total", "Open PRs", ["repo"])
STALE_PRS = Gauge("grimoire_stale_pull_requests_total", "Stale PRs", ["repo"])
WORKFLOW_STATUS = Gauge(
    "grimoire_workflow_status",
    "Workflow status (1=success, 0=failure)",
    ["repo", "workflow", "branch"],
)
CHECK_STATUS = Gauge(
    "grimoire_check_status",
    "Check status (1=pass, 0=fail)",
    ["repo", "check", "branch"],
)

# ---------------------------------------------------------------------------
# Performance histograms
# ---------------------------------------------------------------------------

CHECK_DURATION = Histogram(
    "grimoire_check_run_duration_seconds", "Check execution time", ["check"]
)
ACTION_DURATION = Histogram(
    "grimoire_action_run_duration_seconds", "Action execution time", ["action"]
)
DATA_REFRESH_DURATION = Histogram(
    "grimoire_data_refresh_duration_seconds", "Full data refresh cycle time"
)

# ---------------------------------------------------------------------------
# GitHub API metrics
# ---------------------------------------------------------------------------

API_REQUESTS = Counter(
    "grimoire_github_api_requests_total", "Total API calls", ["endpoint", "status"]
)
RATE_LIMIT_REMAINING = Gauge("grimoire_github_api_rate_limit_remaining", "Rate limit remaining")
RATE_LIMIT_RESET = Gauge("grimoire_github_api_rate_limit_reset", "Rate limit reset timestamp")

# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------

router = APIRouter(tags=["observability"])


@router.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def update_repo_metrics(stats_list: list[RepositoryStats]) -> None:
    """Update all per-repo gauge metrics after a data refresh."""
    REPOS_TOTAL.set(len(stats_list))
    for stats in stats_list:
        repo = stats.full_name
        OPEN_ISSUES.labels(repo=repo).set(stats.open_issues)
        STALE_ISSUES.labels(repo=repo).set(stats.stale_issues)
        OPEN_PRS.labels(repo=repo).set(stats.open_pull_requests)
        STALE_PRS.labels(repo=repo).set(stats.stale_pull_requests)
        for wf in stats.workflows:
            val = 1 if wf.status == "success" else 0
            WORKFLOW_STATUS.labels(repo=repo, workflow=wf.name, branch=wf.branch).set(val)


def update_check_metrics(
    check_slug: str, repo: str, branch: str, passed: bool, duration_seconds: float
) -> None:
    """Update check metrics after execution."""
    CHECK_STATUS.labels(repo=repo, check=check_slug, branch=branch).set(1 if passed else 0)
    CHECK_DURATION.labels(check=check_slug).observe(duration_seconds)


def update_action_metrics(action_slug: str, duration_seconds: float) -> None:
    """Update action metrics after execution."""
    ACTION_DURATION.labels(action=action_slug).observe(duration_seconds)


def update_rate_limit_metrics(remaining: int, reset_timestamp: int) -> None:
    """Update GitHub rate limit metrics."""
    RATE_LIMIT_REMAINING.set(remaining)
    RATE_LIMIT_RESET.set(reset_timestamp)
