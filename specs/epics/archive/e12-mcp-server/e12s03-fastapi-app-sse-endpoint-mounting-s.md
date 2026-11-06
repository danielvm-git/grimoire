# e12s03 — FastAPI App SSE Endpoint Mounting & Security

**type:** feature
**risk:** P1
**context:** e12-mcp-server
**bcps:** 1

## Context

The MCP server is only useful once it is reachable from the running FastAPI app, and a
network-reachable endpoint needs an authentication gate. This story covers mounting and the
token guard.

## Requirements

#### ADDED: `mount_mcp_server(app, mcp, endpoint_path="/mcp", token=None)`
- Builds the SSE ASGI app via `mcp.sse_app(transport_security=...)`.
- With a token: mounts the SSE app behind `MCPAuthMiddleware`.
- Without a token: mounts the SSE app unauthenticated **and logs a warning** naming the
  consequence, so an operator can never be silently unprotected.

#### ADDED: `MCPAuthMiddleware` — pure ASGI middleware
- Accepts `X-MCP-Token` or `Authorization: Bearer <token>`.
- Compares with `secrets.compare_digest` (constant time, no timing oracle).
- Returns HTTP 401 with a JSON body when the credential is missing or wrong.
- **Must not be a `BaseHTTPMiddleware`.** That class buffers the response and asserts every
  downstream message is `http.response.body`, so wrapping the SSE stream crashed the ASGI app
  with `AssertionError: Unexpected message` on every client disconnect.

#### ADDED: mount gate in `src/grimoire/app.py`
`if config.mcp.enabled:` → create and mount the server, then log
`MCP server mounted at <path> (token auth: enabled|disabled)`.

## Acceptance Criteria

```gherkin
Feature: MCP endpoint mounting and authentication

  Scenario: Mounting without a token
    Given mcp.enabled is True and mcp.token is empty
    When the app starts
    Then /mcp/messages/ is reachable without credentials
    And a WARNING containing "without authentication" is logged

  Scenario: Token authentication is enforced
    Given mcp.token is "secret-token-123"
    When a request arrives with no credential
    Then the response is 401
    When a request arrives with X-MCP-Token "wrong-token"
    Then the response is 401
    When a request arrives with Authorization "Basic dXNlcjpwYXNz"
    Then the response is 401
    When a request arrives with Authorization "Bearer secret-token-123"
    Then the request reaches the MCP app
    When a request arrives with X-MCP-Token "  secret-token-123  "
    Then the whitespace is stripped and the request reaches the MCP app

  Scenario: SSE survives a client disconnect
    Given a mounted MCP endpoint with a token
    When an SSE client connects and then disconnects
    Then the ASGI app raises no AssertionError
    And the response stream is forwarded verbatim, not buffered

  Scenario: Disabled module
    Given mcp.enabled is False
    When the app starts
    Then /mcp/messages/ returns 404
```

## Steps

1. **Mounting** — mount the SSE app at `config.mcp.endpoint_path`, gated by `enabled`.
   → verify: `uv run pytest tests/test_mcp/test_server.py -v`
2. **Security** — implement the constant-time token guard as pure ASGI middleware.
   → verify: `uv run pytest tests/test_mcp/test_server.py -v`
3. **Cold start** — start the server and confirm 401 without a token and a live SSE stream with one.
   → verify: `just check`

## Verification

```bash
uv run pytest tests/test_mcp/test_server.py -v
uv run pytest tests/test_mcp/test_server.py --cov=grimoire.mcp.server --cov-report=term-missing
just check
```

## Provenance

`specs/bugs/registry.yaml` — `mcp-auth-middleware-breaks-sse-stream`.
`specs/adr/ADR-006-mcp-server-sse-token-auth.md`.
