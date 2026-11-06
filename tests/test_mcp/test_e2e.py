# story: e12s04
"""End-to-end integration tests for Grimoire MCP Server and user documentation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from grimoire.app import create_app


def _write_config(
    tmp_path: Path, *, enabled: bool = True, token: str | None = None
) -> Path:
    config_file = tmp_path / "config.yaml"
    mcp_lines = f"mcp:\n  enabled: {'true' if enabled else 'false'}\n"
    if token:
        mcp_lines += f"  token: {token}\n"
    config_file.write_text(
        "github:\n"
        "  token: test_token\n"
        "repositories:\n"
        "  - repo: owner/repo\n"
        f"data_dir: {tmp_path / 'data'}\n"
        f"workspace_dir: {tmp_path / 'workspace'}\n"
        f"database_path: {tmp_path / 'db.sqlite'}\n"
        f"log_file: {tmp_path / 'log'}\n" + mcp_lines
    )
    (tmp_path / "data" / "checks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "actions").mkdir(parents=True, exist_ok=True)
    return config_file


@pytest.mark.asyncio
async def test_mcp_e2e_lifespan_mounted_with_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FastAPI app mounts MCP server with token authentication during lifespan."""
    config_file = _write_config(tmp_path, enabled=True, token="secret-mcp-token")
    monkeypatch.setenv("GRIMOIRE_CONFIG", str(config_file))

    mock_client = MagicMock()
    mock_client._engine = MagicMock()
    mock_client.close = AsyncMock()

    with (
        patch("grimoire.app.GitHubClient", return_value=mock_client),
        patch("grimoire.app.AsyncIOScheduler"),
        patch("grimoire.app.WorkspaceManager") as mock_ws_cls,
        patch(
            "grimoire.app.refresh_all_stats",
            new_callable=AsyncMock,
            return_value=([], []),
        ),
    ):
        mock_ws = MagicMock()
        mock_ws.setup = AsyncMock()
        mock_ws.sync_all = AsyncMock()
        mock_ws.workspace_dir = tmp_path / "workspace"
        mock_ws_cls.return_value = mock_ws

        app = create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # 1. Unauthenticated request should be rejected by MCPAuthMiddleware (401)
                resp_unauth = await client.get("/mcp/messages/")
                assert resp_unauth.status_code == 401

                # 2. Wrong token should be rejected (401)
                resp_wrong = await client.get(
                    "/mcp/messages/", headers={"X-MCP-Token": "wrong-token"}
                )
                assert resp_wrong.status_code == 401

                # 3. Valid Bearer token reaches FastMCP app (returns 400 for missing session)
                resp_bearer = await client.post(
                    "/mcp/messages/",
                    headers={"Authorization": "Bearer secret-mcp-token"},
                )
                assert resp_bearer.status_code == 400

                # 4. Valid X-MCP-Token header reaches FastMCP app
                resp_header = await client.post(
                    "/mcp/messages/",
                    headers={"X-MCP-Token": "secret-mcp-token"},
                )
                assert resp_header.status_code == 400


@pytest.mark.asyncio
async def test_mcp_e2e_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When mcp.enabled is False, /mcp route is not mounted."""
    config_file = _write_config(tmp_path, enabled=False)
    monkeypatch.setenv("GRIMOIRE_CONFIG", str(config_file))

    mock_client = MagicMock()
    mock_client._engine = MagicMock()
    mock_client.close = AsyncMock()

    with (
        patch("grimoire.app.GitHubClient", return_value=mock_client),
        patch("grimoire.app.AsyncIOScheduler"),
        patch("grimoire.app.WorkspaceManager") as mock_ws_cls,
        patch(
            "grimoire.app.refresh_all_stats",
            new_callable=AsyncMock,
            return_value=([], []),
        ),
    ):
        mock_ws = MagicMock()
        mock_ws.setup = AsyncMock()
        mock_ws.sync_all = AsyncMock()
        mock_ws.workspace_dir = tmp_path / "workspace"
        mock_ws_cls.return_value = mock_ws

        app = create_app()
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/mcp/messages/")
                assert resp.status_code == 404


def test_mcp_documentation_accuracy() -> None:
    """User documentation accurately reflects all MCP tools and configuration parameters."""
    doc_path = Path("docs/user/reference/mcp.md")
    assert doc_path.exists(), "docs/user/reference/mcp.md must exist"

    content = doc_path.read_text()

    # Tools check
    expected_tools = [
        "list_repositories",
        "list_checks",
        "get_repo_checks_status",
        "get_check_backlog",
        "run_repo_checks",
    ]
    for tool in expected_tools:
        assert tool in content, f"Tool {tool} not documented in mcp.md"

    # Configuration options check
    assert "enabled" in content
    assert "token" in content
    assert "endpoint_path" in content
