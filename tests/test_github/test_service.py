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
    refresh_all_stats,
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
    respx.get("https://api.github.com/repos/owner/repo1/branches/main").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "main",
                "commit": {
                    "sha": "abc",
                    "commit": {"committer": {"date": fresh_date}},
                },
            },
            headers={"X-RateLimit-Remaining": "4996", "X-RateLimit-Limit": "5000"},
        )
    )
    respx.get("https://api.github.com/repos/owner/repo1/branches").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "main",
                    "commit": {"sha": "abc", "commit": {"committer": {"date": fresh_date}}},
                },
                {
                    "name": "old-feature",
                    "commit": {"sha": "def", "commit": {"committer": {"date": old_date}}},
                },
            ],
            headers={"X-RateLimit-Remaining": "4995", "X-RateLimit-Limit": "5000"},
        )
    )

    repo = TrackedRepository(full_name="owner/repo1", default_branch="main", branches=["main"])
    staleness = StalenessConfig(issues_days=365, pull_requests_days=30)
    stats = await fetch_repository_stats(repo, client, staleness)

    assert stats.open_issues == 2
    assert stats.stale_issues == 1  # only the 400-day-old one
    assert stats.open_pull_requests == 2
    assert stats.stale_pull_requests == 1  # only the 400-day-old one
    assert stats.last_commit_at is not None
    assert stats.total_branches == 2
    assert stats.stale_branches == 1  # the old-feature branch


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
            last_commit_at=now,
            total_branches=5,
            stale_branches=2,
        )
    ]

    await save_stats_to_db(engine, stats_list, repos)

    # Verify records in DB
    async with AsyncSession(engine) as session:
        cached = (await session.exec(select(CachedRepository))).all()
        assert len(cached) == 1
        assert cached[0].full_name == "owner/repo1"
        assert json.loads(cached[0].branches_json) == ["main", "develop"]
        assert cached[0].total_branches == 5
        assert cached[0].stale_branches == 2
        assert cached[0].last_commit_at is not None

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
    assert loaded_stats[0].total_branches == 5
    assert loaded_stats[0].stale_branches == 2
    assert loaded_stats[0].last_commit_at is not None


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


# ---------------------------------------------------------------------------
# refresh_all_stats — 304 fallback
# ---------------------------------------------------------------------------


@respx.mock
async def test_refresh_falls_back_to_cache_on_304(
    client: GitHubClient, engine: AsyncEngine
) -> None:
    """When repo resolution returns nothing (all 304s), cached repos are used."""
    # Pre-populate the DB with cached data
    repos = [TrackedRepository(full_name="myorg/svc", default_branch="main", branches=["main"])]
    now = datetime.now(UTC)
    stats_list = [
        RepositoryStats(
            full_name="myorg/svc",
            default_branch="main",
            open_issues=3,
            fetched_at=now,
        )
    ]
    await save_stats_to_db(engine, stats_list, repos)

    # Mock team endpoint returning 304 (ETag hit)
    respx.get("https://api.github.com/orgs/myorg/teams/backend/repos").mock(
        return_value=httpx.Response(
            304,
            headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
        )
    )

    # Mock the per-repo endpoints (also 304)
    for pattern in [
        "/repos/myorg/svc/issues",
        "/repos/myorg/svc/pulls",
        "/repos/myorg/svc/actions/workflows",
        "/repos/myorg/svc/branches/main",
        "/repos/myorg/svc/branches",
    ]:
        respx.get(f"https://api.github.com{pattern}").mock(
            return_value=httpx.Response(
                304,
                headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
            )
        )

    config = _make_config(repos=[TeamRepoSource(team="myorg/backend")])
    result_repos, result_stats = await refresh_all_stats(config, client)

    # Should fall back to cached repos rather than returning empty
    assert len(result_repos) == 1
    assert result_repos[0].full_name == "myorg/svc"
    assert len(result_stats) == 1


# ---------------------------------------------------------------------------
# prune_removed_repos
# ---------------------------------------------------------------------------


async def test_prune_removes_repos_not_in_config(engine: AsyncEngine) -> None:
    """Repos in DB but not in config should be deleted."""
    from grimoire.github.service import prune_removed_repos

    # Seed DB with two repos
    repo_a = TrackedRepository(full_name="org/keep", default_branch="main", branches=["main"])
    repo_b = TrackedRepository(full_name="org/remove", default_branch="main", branches=["main"])
    stats = [
        RepositoryStats(full_name="org/keep", default_branch="main"),
        RepositoryStats(full_name="org/remove", default_branch="main"),
    ]
    await save_stats_to_db(engine, stats, [repo_a, repo_b])

    # Config only has org/keep
    config = _make_config(repos=[StaticRepoSource(repo="org/keep")])
    pruned = await prune_removed_repos(engine, config)
    assert pruned == 1

    # Verify only org/keep remains
    repos, _ = await load_stats_from_db(engine)
    assert [r.full_name for r in repos] == ["org/keep"]


async def test_prune_skipped_with_team_sources(engine: AsyncEngine) -> None:
    """Pruning should be skipped when team sources are present."""
    from grimoire.github.service import prune_removed_repos

    # Seed DB with a repo
    repo = TrackedRepository(full_name="org/repo", default_branch="main", branches=["main"])
    await save_stats_to_db(
        engine, [RepositoryStats(full_name="org/repo", default_branch="main")], [repo]
    )

    # Config has a team source — can't know full set, so skip pruning
    config = _make_config(repos=[TeamRepoSource(team="org/myteam")])
    pruned = await prune_removed_repos(engine, config)
    assert pruned == 0

    # Repo should still be there
    repos, _ = await load_stats_from_db(engine)
    assert len(repos) == 1
