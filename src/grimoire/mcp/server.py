"""MCPServer initialization and FastAPI mounting for Grimoire."""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from grimoire.mcp.tools import MCPToolHandlers

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.checks.loader import CheckDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager


class MCPAuthMiddleware:
    """Token authentication for the MCP SSE endpoint, as pure ASGI middleware.

    Deliberately not a starlette ``BaseHTTPMiddleware``: that class buffers the response and
    asserts every downstream message is ``http.response.body``, so wrapping the SSE stream
    crashed the app with ``AssertionError: Unexpected message`` on every client disconnect.
    Provenance: specs/bugs/registry.yaml mcp-auth-middleware-breaks-sse-stream.
    """

    def __init__(self, app: ASGIApp, required_token: str) -> None:
        self.app = app
        self.required_token = required_token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._token_matches(Request(scope)):
            await self.app(scope, receive, send)
            return

        unauthorized = JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: Invalid or missing MCP token."},
        )
        await unauthorized(scope, receive, send)

    def _token_matches(self, request: Request) -> bool:
        """Compare the supplied X-MCP-Token or Bearer credential in constant time."""
        auth_header = request.headers.get("Authorization", "")
        token_header = request.headers.get("X-MCP-Token", "").strip()

        bearer_token = ""
        if auth_header.lower().startswith("bearer "):
            bearer_token = auth_header[7:].strip()

        provided_token = token_header or bearer_token
        return secrets.compare_digest(provided_token, self.required_token)


def create_mcp_server(
    engine: AsyncEngine,
    checks: list[CheckDefinition],
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
) -> MCPServer:
    """Create and configure an MCPServer instance for Grimoire."""
    handlers = MCPToolHandlers(
        engine=engine, checks=checks, repos=repos, workspace=workspace
    )
    mcp = MCPServer("Grimoire")

    @mcp.tool(
        name="list_repositories",
        description="List all tracked repositories in Grimoire.",
    )
    async def list_repositories() -> list[dict[str, Any]]:
        return await handlers.list_repositories()

    @mcp.tool(
        name="list_checks",
        description="List all loaded check definitions in Grimoire.",
    )
    async def list_checks() -> list[dict[str, Any]]:
        return await handlers.list_checks()

    @mcp.tool(
        name="get_repo_checks_status",
        description="Query overall check passing/failing status and latest result summary for a repository.",
    )
    async def get_repo_checks_status(
        repo: str, refresh: bool = False
    ) -> dict[str, Any]:
        return await handlers.get_repo_checks_status(repo=repo, refresh=refresh)

    @mcp.tool(
        name="get_check_backlog",
        description="Get the backlog of failing or missing checks for a repository, including failure logs.",
    )
    async def get_check_backlog(repo: str, refresh: bool = False) -> dict[str, Any]:
        return await handlers.get_check_backlog_data(repo=repo, refresh=refresh)

    @mcp.tool(
        name="run_repo_checks",
        description="Trigger execution of checks for a repository on demand.",
    )
    async def run_repo_checks(
        repo: str, check_slug: str | None = None
    ) -> dict[str, Any]:
        return await handlers.run_repo_checks(repo=repo, check_slug=check_slug)

    return mcp


def mount_mcp_server(
    app: FastAPI,
    mcp: MCPServer,
    endpoint_path: str = "/mcp",
    token: str | None = None,
) -> None:
    """Mount the MCPServer SSE application onto the FastAPI app."""
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
    sse_app = mcp.sse_app(transport_security=transport_security)

    if token:
        app.mount(endpoint_path, MCPAuthMiddleware(app=sse_app, required_token=token))
    else:
        logger.warning(
            "MCP endpoint mounted at %s without authentication "
            "(token is empty); set mcp.token to require auth",
            endpoint_path,
        )
        app.mount(endpoint_path, sse_app)
