# story: e12s03
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
from grimoire.mcp.server import (
    MCPAuthMiddleware,
    create_mcp_server,
    mount_mcp_server,
)
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

        # Request with whitespace-padded X-MCP-Token should also pass auth middleware
        res_padded_auth = await client.post(
            "/mcp/messages/", headers={"X-MCP-Token": "  secret-token-123  "}
        )
        assert res_padded_auth.status_code == 400

        # Request with correct Bearer header should pass auth middleware
        res_bearer_auth = await client.post(
            "/mcp/messages/", headers={"Authorization": "Bearer secret-token-123"}
        )
        assert res_bearer_auth.status_code == 400

        # Request to /mcp/sse without token should fail with 401
        res_sse_unauth = await client.get("/mcp/sse")
        assert res_sse_unauth.status_code == 401

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


class _ReconnectingSseApp:
    """ASGI app that emits a second response.start, as the SSE transport does after a disconnect."""

    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": True})
        # The SSE stream ends with the client disconnecting, and the transport re-emits a start.
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-length", b"0")],
            }
        )
        await send({"type": "http.response.body", "body": b"", "more_body": False})


def _http_scope(headers: list[tuple[bytes, bytes]]) -> dict[str, object]:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/mcp/sse",
        "raw_path": b"/mcp/sse",
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 80),
    }


@pytest.mark.asyncio
async def test_auth_middleware_forwards_streaming_disconnect_messages() -> None:
    """A streamed response that re-emits response.start must pass through untouched.

    BaseHTTPMiddleware buffers the response and asserts every downstream message is
    http.response.body, so wrapping the SSE transport crashed the app on every client
    disconnect. Provenance: specs/bugs/registry.yaml mcp-auth-middleware-breaks-sse-stream.
    """
    inner = _ReconnectingSseApp()
    guarded = MCPAuthMiddleware(app=inner, required_token="secret-token-123")
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await guarded(
        _http_scope([(b"x-mcp-token", b"secret-token-123")]),
        receive,
        send,
    )

    start_messages = [m for m in sent if m["type"] == "http.response.start"]
    assert len(start_messages) == 2, "both response starts must be forwarded verbatim"


@pytest.mark.asyncio
async def test_auth_middleware_rejects_missing_token_without_calling_app() -> None:
    """An unauthenticated request never reaches the SSE app."""
    inner = _ReconnectingSseApp()
    guarded = MCPAuthMiddleware(app=inner, required_token="secret-token-123")
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    await guarded(_http_scope([]), receive, send)

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 401
