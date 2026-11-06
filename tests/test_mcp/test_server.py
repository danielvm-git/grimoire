# story: e12s01
"""Integration tests for MCPServer mounting and security middleware."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from grimoire.checks.loader import CheckDefinition
from grimoire.database import create_tables, get_engine
from grimoire.mcp.server import create_mcp_server, mount_mcp_server
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec
from grimoire.workspace.manager import WorkspaceManager


def _check() -> CheckDefinition:
    return CheckDefinition(
        slug="lint",
        name="Linting",
        description="Run linter",
        severity="error",
        targets=TargetSpec(list=["lucabello/grimoire"]),
        script="exit 0",
        file_path=Path("/tmp/lint.yaml"),
    )


def _repo() -> TrackedRepository:
    return TrackedRepository(
        full_name="lucabello/grimoire",
        default_branch="main",
        branches=["main"],
    )


def _workspace(tmp_path: Path) -> WorkspaceManager:
    mock_config = MagicMock()
    mock_config.workspace_dir = tmp_path / "workspace"
    return WorkspaceManager(config=mock_config)


@pytest.mark.asyncio
async def test_create_and_mount_mcp_server(tmp_path: Path):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    mcp = create_mcp_server(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo()],
        workspace=wm,
    )
    assert mcp is not None

    app = FastAPI()
    mount_mcp_server(app=app, mcp=mcp, endpoint_path="/mcp")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        # Check endpoint accessibility via POST /mcp/messages/ (returns 400 when session is missing)
        response = await client.post("/mcp/messages/")
        assert response.status_code == 400

    await db_engine.dispose()


@pytest.mark.asyncio
async def test_mcp_server_token_auth(tmp_path: Path):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    mcp = create_mcp_server(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo()],
        workspace=wm,
    )

    app = FastAPI()
    mount_mcp_server(app=app, mcp=mcp, endpoint_path="/mcp", token="secret-token-123")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        # Request without token should fail with 401
        res_unauth = await client.get("/mcp/messages/")
        assert res_unauth.status_code == 401

        # Request with wrong token should fail with 401
        res_wrong = await client.get(
            "/mcp/messages/", headers={"X-MCP-Token": "wrong-token"}
        )
        assert res_wrong.status_code == 401

        # Request with non-Bearer auth should fail with 401
        res_basic = await client.get(
            "/mcp/messages/", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert res_basic.status_code == 401

        # Request with wrong Bearer token should fail with 401
        res_wrong_bearer = await client.get(
            "/mcp/messages/", headers={"Authorization": "Bearer wrong-token"}
        )
        assert res_wrong_bearer.status_code == 401

        # Request with correct X-MCP-Token header should pass auth middleware (reaches app -> 400 missing session)
        res_auth = await client.post(
            "/mcp/messages/", headers={"X-MCP-Token": "secret-token-123"}
        )
        assert res_auth.status_code == 400

        # Request with correct Bearer header should pass auth middleware
        res_bearer_auth = await client.post(
            "/mcp/messages/", headers={"Authorization": "Bearer secret-token-123"}
        )
        assert res_bearer_auth.status_code == 400

    await db_engine.dispose()


@pytest.mark.asyncio
async def test_mcp_server_tools_registered_and_invoked(tmp_path: Path):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    mcp = create_mcp_server(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo()],
        workspace=wm,
    )

    # 1. list_repositories
    res_repos = await mcp.call_tool("list_repositories", {})
    assert res_repos.is_error is False

    # 2. list_checks
    res_checks = await mcp.call_tool("list_checks", {})
    assert res_checks.is_error is False

    # 3. get_repo_checks_status
    res_status = await mcp.call_tool(
        "get_repo_checks_status", {"repo": "lucabello/grimoire"}
    )
    assert res_status.is_error is False

    # 4. get_check_backlog
    res_backlog = await mcp.call_tool(
        "get_check_backlog", {"repo": "lucabello/grimoire"}
    )
    assert res_backlog.is_error is False

    # 5. run_repo_checks
    res_run = await mcp.call_tool(
        "run_repo_checks", {"repo": "lucabello/grimoire", "check_slug": "lint"}
    )
    assert res_run.is_error is False

    await db_engine.dispose()


def test_empty_token_warns(caplog: pytest.LogCaptureFixture) -> None:
    """Mounting without a token must be visible in logs (F20)."""
    app = FastAPI()
    fake = MagicMock()
    fake.sse_app.return_value = FastAPI()

    with caplog.at_level(logging.WARNING, logger="grimoire.mcp.server"):
        mount_mcp_server(app=app, mcp=fake, token=None)

    assert "without authentication" in caplog.text
