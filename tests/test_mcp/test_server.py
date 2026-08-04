"""Integration tests for MCPServer mounting and security middleware."""

from __future__ import annotations

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

        # Request with correct X-MCP-Token header should pass auth middleware (reaches app -> 400 missing session)
        res_auth = await client.post(
            "/mcp/messages/", headers={"X-MCP-Token": "secret-token-123"}
        )
        assert res_auth.status_code == 400
