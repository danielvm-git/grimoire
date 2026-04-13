"""Tests for Prometheus metrics."""

from __future__ import annotations

from httpx import AsyncClient
from prometheus_client import REGISTRY

from grimoire.models import RepositoryStats, WorkflowStatus
from grimoire.observability.metrics import (
    OPEN_ISSUES,
    OPEN_PRS,
    REPOS_TOTAL,
    STALE_ISSUES,
    STALE_PRS,
    WORKFLOW_STATUS,
    update_check_metrics,
    update_repo_metrics,
)


async def test_metrics_endpoint_returns_200(async_client: AsyncClient) -> None:
    """GET /metrics returns 200 with prometheus content type."""
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    # Should contain at least one of our custom metrics
    assert b"grimoire_" in resp.content


async def test_update_repo_metrics_sets_gauges() -> None:
    """update_repo_metrics correctly sets all per-repo gauges."""
    stats_list = [
        RepositoryStats(
            full_name="org/alpha",
            default_branch="main",
            open_issues=5,
            stale_issues=2,
            open_pull_requests=3,
            stale_pull_requests=1,
            workflows=[
                WorkflowStatus(
                    name="CI",
                    branch="main",
                    status="success",
                    url="https://example.com",
                ),
                WorkflowStatus(
                    name="Deploy",
                    branch="main",
                    status="failure",
                    url="https://example.com",
                ),
            ],
        ),
        RepositoryStats(
            full_name="org/beta",
            default_branch="main",
            open_issues=10,
            stale_issues=0,
            open_pull_requests=0,
            stale_pull_requests=0,
        ),
    ]

    update_repo_metrics(stats_list)

    assert REPOS_TOTAL._value.get() == 2  # type: ignore[union-attr]
    assert OPEN_ISSUES.labels(repo="org/alpha")._value.get() == 5  # type: ignore[union-attr]
    assert STALE_ISSUES.labels(repo="org/alpha")._value.get() == 2  # type: ignore[union-attr]
    assert OPEN_PRS.labels(repo="org/alpha")._value.get() == 3  # type: ignore[union-attr]
    assert STALE_PRS.labels(repo="org/alpha")._value.get() == 1  # type: ignore[union-attr]
    assert OPEN_ISSUES.labels(repo="org/beta")._value.get() == 10  # type: ignore[union-attr]

    # Workflow gauges
    assert (
        WORKFLOW_STATUS.labels(repo="org/alpha", workflow="CI", branch="main")._value.get() == 1  # type: ignore[union-attr]
    )
    assert (
        WORKFLOW_STATUS.labels(repo="org/alpha", workflow="Deploy", branch="main")._value.get()
        == 0  # type: ignore[union-attr]
    )


async def test_update_check_metrics() -> None:
    """update_check_metrics sets status gauge and records histogram."""
    update_check_metrics(
        check_slug="lint",
        repo="org/alpha",
        branch="main",
        passed=True,
        duration_seconds=1.5,
    )

    # Verify the check status gauge was set
    from grimoire.observability.metrics import CHECK_STATUS

    val = CHECK_STATUS.labels(repo="org/alpha", check="lint", branch="main")._value.get()  # type: ignore[union-attr]
    assert val == 1

    # Verify histogram recorded a sample
    sample = REGISTRY.get_sample_value(
        "grimoire_check_run_duration_seconds_count", {"check": "lint"}
    )
    assert sample is not None
    assert sample >= 1
