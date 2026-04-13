"""Tests for the GitHub service layer."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.config import (
    GitHubConfig,
    GrimoireConfig,
    StalenessConfig,
    StaticRepoSource,
    TeamRepoSource,
)
from grimoire.database import (
    CachedRepository,
    CachedWorkflowStatus,
    create_tables,
    get_engine,
)
from grimoire.github.client import GitHubClient
from grimoire.github.service import (
    fetch_repository_stats,
    load_stats_from_db,
    resolve_repositories,
    save_stats_to_db,
)
from grimoire.models import RepositoryStats, TrackedRepository, WorkflowStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine(tmp_path) -> AsyncEngine:
    db_path = str(tmp_path / "test.db")
    eng = await get_engine(db_path)
    await create_tables(eng)
    return eng


@pytest.fixture
async def client(engine: AsyncEngine) -> GitHubClient:
    c = GitHubClient(token="ghp_test", engine=engine, backoff_factors=(0.0, 0.0, 0.0))
    yield c  # type: ignore[misc]
    await c.close()


def _make_config(
    repos: list[StaticRepoSource | TeamRepoSource] | None = None,
    staleness: StalenessConfig | None = None,
) -> GrimoireConfig:
    return GrimoireConfig(
        github=GitHubConfig(token="ghp_test"),
        repositories=repos or [StaticRepoSource(repo="owner/repo1")],
        staleness=staleness or StalenessConfig(),
    )


# ---------------------------------------------------------------------------
# resolve_repositories — static
# ---------------------------------------------------------------------------


@respx.mock
async def test_resolve_static_repos(client: GitHubClient) -> None:
    respx.get("https://api.github.com/repos/owner/repo1").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "owner/repo1",
                "default_branch": "main",
                "archived": False,
            },
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
        )
    )
    config = _make_config(
        repos=[StaticRepoSource(repo="owner/repo1", branches=["main", "develop"])]
    )
    repos = await resolve_repositories(config, client)
    assert len(repos) == 1
    assert repos[0].full_name == "owner/repo1"
    assert repos[0].branches == ["main", "develop"]
    assert repos[0].source == "static"


@respx.mock
async def test_resolve_static_uses_default_branch(client: GitHubClient) -> None:
    """When no branches specified, use the repo's default_branch."""
    respx.get("https://api.github.com/repos/owner/repo1").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "owner/repo1",
                "default_branch": "develop",
                "archived": False,
            },
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
        )
    )
    config = _make_config(repos=[StaticRepoSource(repo="owner/repo1")])
    repos = await resolve_repositories(config, client)
    assert len(repos) == 1
    assert repos[0].branches == ["develop"]


@respx.mock
async def test_resolve_skips_archived(client: GitHubClient) -> None:
    respx.get("https://api.github.com/repos/owner/archived").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "owner/archived",
                "default_branch": "main",
                "archived": True,
            },
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
        )
    )
    config = _make_config(repos=[StaticRepoSource(repo="owner/archived")])
    repos = await resolve_repositories(config, client)
    assert len(repos) == 0


# ---------------------------------------------------------------------------
# resolve_repositories — team
# ---------------------------------------------------------------------------


@respx.mock
async def test_resolve_team_repos(client: GitHubClient) -> None:
    respx.get("https://api.github.com/orgs/myorg/teams/backend/repos").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "full_name": "myorg/service-a",
                    "default_branch": "main",
                    "archived": False,
                },
                {
                    "full_name": "myorg/service-b",
                    "default_branch": "main",
                    "archived": False,
                },
                {
                    "full_name": "myorg/old-repo",
                    "default_branch": "main",
                    "archived": True,
                },
            ],
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
        )
    )
    config = _make_config(
        repos=[TeamRepoSource(team="myorg/backend", exclude=["myorg/service-b"])]
    )
    repos = await resolve_repositories(config, client)
    assert len(repos) == 1
    assert repos[0].full_name == "myorg/service-a"
    assert repos[0].source == "team:myorg/backend"


# ---------------------------------------------------------------------------
# fetch_repository_stats — staleness
# ---------------------------------------------------------------------------


@respx.mock
async def test_fetch_stats_stale_detection(client: GitHubClient) -> None:
    now = datetime.now(UTC)
    old_date = (now - timedelta(days=400)).isoformat()
    fresh_date = (now - timedelta(days=10)).isoformat()

    respx.get("https://api.github.com/repos/owner/repo1/issues").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "Old issue",
                    "updated_at": old_date,
                    "created_at": old_date,
                },
                {
                    "number": 2,
                    "title": "Fresh issue",
                    "updated_at": fresh_date,
                    "created_at": fresh_date,
                },
            ],
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
        )
    )
    respx.get("https://api.github.com/repos/owner/repo1/pulls").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"number": 10, "title": "Old PR", "updated_at": old_date, "created_at": old_date},
                {
                    "number": 11,
                    "title": "Fresh PR",
                    "updated_at": fresh_date,
                    "created_at": fresh_date,
                },
            ],
            headers={"X-RateLimit-Remaining": "4998", "X-RateLimit-Limit": "5000"},
        )
    )
    respx.get("https://api.github.com/repos/owner/repo1/actions/workflows").mock(
        return_value=httpx.Response(
            200,
            json={"total_count": 0, "workflows": []},
            headers={"X-RateLimit-Remaining": "4997", "X-RateLimit-Limit": "5000"},
        )
    )

    repo = TrackedRepository(full_name="owner/repo1", default_branch="main", branches=["main"])
    staleness = StalenessConfig(issues_days=365, pull_requests_days=30)
    stats = await fetch_repository_stats(repo, client, staleness)

    assert stats.open_issues == 2
    assert stats.stale_issues == 1  # only the 400-day-old one
    assert stats.open_pull_requests == 2
    assert stats.stale_pull_requests == 1  # only the 400-day-old one


# ---------------------------------------------------------------------------
# DB round-trip: save + load
# ---------------------------------------------------------------------------


async def test_save_and_load_stats(engine: AsyncEngine) -> None:
    repos = [
        TrackedRepository(
            full_name="owner/repo1",
            default_branch="main",
            branches=["main", "develop"],
            source="static",
        )
    ]
    now = datetime.now(UTC)
    stats_list = [
        RepositoryStats(
            full_name="owner/repo1",
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
                    url="https://github.com/owner/repo1/actions/workflows/ci.yml",
                    run_url="https://github.com/owner/repo1/actions/runs/123",
                )
            ],
            fetched_at=now,
        )
    ]

    await save_stats_to_db(engine, stats_list, repos)

    # Verify records in DB
    async with AsyncSession(engine) as session:
        cached = (await session.exec(select(CachedRepository))).all()
        assert len(cached) == 1
        assert cached[0].full_name == "owner/repo1"
        assert json.loads(cached[0].branches_json) == ["main", "develop"]

        wf_rows = (await session.exec(select(CachedWorkflowStatus))).all()
        assert len(wf_rows) == 1
        assert wf_rows[0].workflow_name == "CI"
        assert wf_rows[0].status == "success"

    # Load back
    loaded_repos, loaded_stats = await load_stats_from_db(engine)
    assert len(loaded_repos) == 1
    assert loaded_repos[0].full_name == "owner/repo1"
    assert loaded_repos[0].branches == ["main", "develop"]
    assert len(loaded_stats) == 1
    assert loaded_stats[0].workflows[0].name == "CI"


async def test_save_replaces_old_data(engine: AsyncEngine) -> None:
    """Saving twice should replace, not duplicate, cached records."""
    repos = [TrackedRepository(full_name="owner/repo1", default_branch="main", branches=["main"])]
    now = datetime.now(UTC)
    stats_v1 = [RepositoryStats(full_name="owner/repo1", default_branch="main", fetched_at=now)]
    stats_v2 = [
        RepositoryStats(
            full_name="owner/repo1",
            default_branch="main",
            open_issues=10,
            fetched_at=now,
        )
    ]

    await save_stats_to_db(engine, stats_v1, repos)
    await save_stats_to_db(engine, stats_v2, repos)

    async with AsyncSession(engine) as session:
        cached = (await session.exec(select(CachedRepository))).all()
        assert len(cached) == 1
