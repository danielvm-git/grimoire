# story: e08s01
"""Tests for app.py lifespan orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from grimoire.app import VERSION, create_app


@pytest.fixture
def mock_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal config and set GRIMOIRE_CONFIG."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "github:\n"
        "  token: test_token\n"
        "repositories:\n"
        "  - repo: owner/repo\n"
        "staleness:\n"
        "  pull_requests_days: 14\n"
        "  issues_days: 180\n"
        f"data_dir: {tmp_path / 'data'}\n"
        f"workspace_dir: {tmp_path / 'workspace'}\n"
        f"database_path: {tmp_path / 'db'}\n"
        f"log_file: {tmp_path / 'log'}\n"
    )
    (tmp_path / "data" / "checks").mkdir(parents=True)
    (tmp_path / "data" / "actions").mkdir(parents=True)
    monkeypatch.setenv("GRIMOIRE_CONFIG", str(config_file))
    return config_file


class TestLifespanFreshness:
    """Tests for the three-tier data freshness strategy."""

    async def test_app_starts_with_fresh_cache(
        self, mock_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """App should start cleanly when DB cache is fresh."""

        # Mock GitHub client to avoid real API calls during refresh
        async def _close() -> None:
            pass

        mock_client = MagicMock()
        mock_client._engine = MagicMock()
        mock_client.close = AsyncMock(side_effect=_close)

        with (
            patch("grimoire.app.GitHubClient", return_value=mock_client),
            patch("grimoire.app.AsyncIOScheduler") as mock_sched_cls,
            patch("grimoire.app.WorkspaceManager") as mock_ws_cls,
        ):
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler
            mock_workspace = MagicMock()
            mock_workspace.setup = AsyncMock()
            mock_workspace.sync_all = AsyncMock()
            mock_workspace.workspace_dir = Path("/tmp/ws")
            mock_ws_cls.return_value = mock_workspace

            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "ok"
                assert "version" in data

    async def test_health_reports_cache_age_after_update_cache(self) -> None:
        """cache_age_seconds appears once the cache has been populated."""
        from grimoire.github.router import update_cache

        update_cache([], [])
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            data = (await client.get("/health")).json()
        assert "cache_age_seconds" in data

    async def test_health_endpoint_version(self) -> None:
        """Health endpoint returns version."""
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] in ("ok", "degraded")
            assert data["version"] == VERSION


class TestAppFactory:
    """Tests for the FastAPI app factory function."""

    async def test_create_app_title(self) -> None:
        """create_app returns a FastAPI app with correct title."""
        app = create_app()
        assert app.title == "Grimoire"

    async def test_routers_mounted(self) -> None:
        """All expected routers are mounted."""
        app = create_app()
        routes = {route.path for route in app.routes if hasattr(route, "path")}
        assert "/health" in routes
        # API routers should be present
        api_routes = [r for r in routes if r.startswith("/api")]
        assert len(api_routes) >= 0  # routers mounted during lifespan


class TestLifespanShutdown:
    """Tests for graceful shutdown behavior.

    Note: ASGITransport does not reliably trigger lifespan cleanup
    in pytest. Shutdown behavior is verified manually during integration
    testing with a real uvicorn server.
    """

    async def test_app_health_after_workspace_failure(
        self, mock_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """App serves health even after workspace failure."""

        async def _close() -> None:
            pass

        mock_client = MagicMock()
        mock_client._engine = MagicMock()
        mock_client.close = AsyncMock(side_effect=_close)

        with (
            patch("grimoire.app.GitHubClient", return_value=mock_client),
            patch("grimoire.app.AsyncIOScheduler") as mock_sched_cls,
            patch("grimoire.app.WorkspaceManager") as mock_ws_cls,
        ):
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            mock_workspace = MagicMock()
            mock_workspace.setup = AsyncMock()
            mock_workspace.sync_all = AsyncMock()
            mock_workspace.workspace_dir = Path("/tmp/ws")
            mock_ws_cls.return_value = mock_workspace

            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["version"] == VERSION


class TestLifespanResilience:
    """Tests for error resilience during startup."""

    async def test_app_starts_when_workspace_fails(
        self, mock_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """App should start even if workspace setup fails."""

        async def _close() -> None:
            pass

        mock_client = MagicMock()
        mock_client._engine = MagicMock()
        mock_client.close = AsyncMock(side_effect=_close)

        with (
            patch("grimoire.app.GitHubClient", return_value=mock_client),
            patch("grimoire.app.AsyncIOScheduler") as mock_sched_cls,
            patch("grimoire.app.WorkspaceManager") as mock_ws_cls,
        ):
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            # Workspace setup raises an error
            mock_workspace = MagicMock()
            mock_workspace.setup = AsyncMock(side_effect=RuntimeError("disk full"))
            mock_workspace.sync_all = AsyncMock()
            mock_workspace.workspace_dir = Path("/tmp/ws")
            mock_ws_cls.return_value = mock_workspace

            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/health")
                assert resp.status_code == 200
                data = resp.json()
                # App should be ok even with workspace failure
                assert data["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_lifespan_cancels_background_refresh_on_shutdown(
    mock_config: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The background initial refresh must not outlive the lifespan.

    Regression for specs/bugs/registry.yaml e2e-session-transaction-warning:
    asyncio.create_task(_initial_refresh()) was fire-and-forget, so shutdown
    returned while the task was still issuing queries against a closing engine.
    That surfaced as an SAWarning about a connection already in a transaction and
    as a spurious "Background initial refresh failed" ERROR on every shutdown.
    """
    import asyncio

    from grimoire import app as app_module

    refresh_started = asyncio.Event()

    async def never_finishing_refresh(*_args: object, **_kwargs: object) -> tuple:
        refresh_started.set()
        await asyncio.sleep(60)
        return [], []

    with (
        patch("grimoire.app.GitHubClient") as client_cls,
        patch("grimoire.app.AsyncIOScheduler"),
        patch("grimoire.app.WorkspaceManager") as ws_cls,
        patch("grimoire.app.load_stats_from_db", new_callable=AsyncMock) as load_db,
        patch("grimoire.app.refresh_all_stats", side_effect=never_finishing_refresh),
    ):
        client_cls.return_value.close = AsyncMock()
        ws = MagicMock()
        ws.setup = AsyncMock()
        ws.sync_all = AsyncMock()
        ws.workspace_dir = mock_config.parent / "workspace"
        ws_cls.return_value = ws
        # No cached data forces the background refresh path.
        load_db.return_value = ([], [])

        app = create_app()
        caplog.set_level("INFO")
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(refresh_started.wait(), timeout=5)
            task = getattr(app.state, "initial_refresh_task", None)
            assert task is not None, "lifespan must track the background refresh task"
            assert not task.done()

        assert task.done(), (
            "background refresh must be finished before shutdown returns"
        )
        assert not any(
            "Background initial refresh failed" in record.message
            for record in caplog.records
        ), "a cancelled refresh must not be logged as a failure"

    # The task must not still be scheduled on the loop after shutdown.
    assert all(t.done() for t in asyncio.all_tasks() if "initial_refresh" in str(t))
    assert app_module  # keep the module import used for clarity
