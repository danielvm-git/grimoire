"""API schema contract tests (e08s04).

Validates that real API responses conform to their declared Pydantic response models.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from grimoire.app import create_app
from grimoire.checks.loader import CheckDefinition
from grimoire.checks.router import set_checks_state
from grimoire.database import CheckResultRecord, create_tables, get_engine
from grimoire.github.router import update_cache
from grimoire.models import RepositoryStats, TrackedRepository
from grimoire.targeting import TargetSpec


@pytest.fixture
def sample_stats() -> RepositoryStats:
    from datetime import datetime, timezone

    return RepositoryStats(
        full_name="acme/repo",
        default_branch="main",
        open_issues=5,
        stale_issues=2,
        open_pull_requests=3,
        stale_pull_requests=1,
        fetched_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_repo() -> TrackedRepository:
    return TrackedRepository(
        full_name="acme/repo",
        default_branch="main",
        branches=["main"],
    )


class TestRepoListContract:
    async def test_response_matches_repo_list_schema(
        self, sample_stats: RepositoryStats, sample_repo: TrackedRepository
    ) -> None:
        """GET /api/repos response validates against RepoListResponse."""
        from grimoire.github.schemas import RepoListResponse

        update_cache([sample_repo], [sample_stats])
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/repos/")
            assert resp.status_code == 200
            data = resp.json()
            # Validate against schema
            RepoListResponse.model_validate(data)
            assert len(data["repositories"]) == 1
            assert data["repositories"][0]["full_name"] == "acme/repo"


class TestRepoDetailContract:
    async def test_response_matches_repo_detail_schema(
        self, sample_stats: RepositoryStats, sample_repo: TrackedRepository
    ) -> None:
        """GET /api/repos/{owner}/{name} validates against RepoDetailResponse."""
        from grimoire.github.schemas import RepoDetailResponse

        update_cache([sample_repo], [sample_stats])
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/repos/acme/repo")
            assert resp.status_code == 200
            data = resp.json()
            RepoDetailResponse.model_validate(data)
            assert data["full_name"] == "acme/repo"
            assert data["open_issues"] == 5


class TestChecksListContract:
    async def test_response_matches_check_list_schema(self, tmp_path: Path) -> None:
        """GET /api/checks response validates against list[CheckListItem]."""
        from grimoire.checks.router import CheckListItem

        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)

        checks = [
            CheckDefinition(
                name="Test",
                slug="test-check",
                description="desc",
                targets=TargetSpec(list=["acme/repo"]),
                script="echo ok",
            )
        ]
        repos = [TrackedRepository(full_name="acme/repo", default_branch="main")]
        ws = type(
            "WS", (), {"get_workdir": lambda s, a, b: tmp_path, "get_env": lambda s: {}}
        )()

        set_checks_state(checks, repos, ws, engine)

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/checks/")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            # Each item should validate
            for item in data:
                CheckListItem.model_validate(item)


class TestChecksResultsContract:
    async def test_response_matches_check_result_schema(self, tmp_path: Path) -> None:
        """GET /api/checks/{slug}/results validates against CheckResultResponse."""
        from datetime import datetime, timezone

        from grimoire.checks.router import CheckResultResponse

        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)

        # Persist a known result
        from sqlmodel.ext.asyncio.session import AsyncSession

        record = CheckResultRecord(
            check_name="Test",
            check_slug="test-check",
            repo_full_name="acme/repo",
            branch="main",
            passed=True,
            output="ok",
            timestamp=datetime.now(timezone.utc),
        )
        async with AsyncSession(engine) as session:
            session.add(record)
            await session.commit()

        checks = [
            CheckDefinition(
                name="Test",
                slug="test-check",
                description="desc",
                targets=TargetSpec(list=["acme/repo"]),
                script="echo ok",
            )
        ]
        repos = [TrackedRepository(full_name="acme/repo", default_branch="main")]
        ws = type(
            "WS",
            (),
            {
                "get_workdir": lambda s, a, b: tmp_path,
                "get_env": lambda s: {"GH_TOKEN": "t"},
            },
        )()

        set_checks_state(checks, repos, ws, engine)

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/checks/test-check/results")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            for item in data:
                CheckResultResponse.model_validate(item)
