# ADR-006: MCP Server over SSE with Optional Bearer Token Authentication

## Status
Accepted

## Context
Grimoire's repository health data, check definitions and check backlogs were only reachable through the web dashboard and the REST API. The product goal for e12 was to let external AI agents query that data directly, so an agent can answer "what is failing in this repo?" without screen-scraping HTML.

Three things had to be decided: the protocol surface, the transport, and the trust boundary.

- Grimoire is a **self-hosted, single-user** dashboard (ADR-003). It has no user accounts, no sessions and no multi-tenancy.
- The existing HTTP surface is FastAPI, and every module is already async.
- Agents are configured by the operator in their own client (Claude Desktop, Antigravity, custom), typically pointing at `http://localhost:8000`.

## Decision

1. **Expose the Model Context Protocol**, implemented with the official `mcp` SDK (`MCPServer`), rather than inventing a bespoke JSON-RPC schema. MCP is the interface agent clients already speak.
2. **Use the SSE transport**, mounted at `config.mcp.endpoint_path` (default `/mcp`), because it is the transport the `mcp` SDK serves for long-lived server→client streams and it needs no extra process. The stream is served by the same uvicorn worker as the dashboard.
3. **Authenticate with an optional shared token**, read from `config.mcp.token` (resolved from `GRIMOIRE_MCP_TOKEN`). A request must present `X-MCP-Token` or `Authorization: Bearer <token>`, compared with `secrets.compare_digest`. The token is optional because a loopback-only self-hosted instance may not need one; when it is absent the endpoint mounts anyway and logs a startup warning naming the consequence.
4. **Gate the whole module behind `mcp.enabled`** (default `true`) so an operator can remove the surface entirely.
5. **Disable DNS-rebinding protection** (`TransportSecuritySettings(enable_dns_rebinding_protection=False)`), because self-hosted deployments are frequently reached by bare IP or a reverse proxy whose `Host` header the SDK's default allowlist rejects.

## Consequences

- **Positive:** Agents get first-class access to check status and backlogs with five tools, reusing `CheckQueryService` rather than duplicating SQL. Auth is a single constant-time comparison with no new dependency. The module is ~120 lines because the SDK owns the protocol.
- **Negative:** `enable_dns_rebinding_protection=False` means that, **when no token is configured**, a browser on the same network could reach `/mcp` via DNS rebinding. This is accepted for the loopback self-hosted case and mitigated operationally by setting `mcp.token`; the risk is recorded in `specs/security/epics/e12/THREAT_MODEL.md` and `specs/security/REVIEW.md`.
- **Negative:** SSE holds a connection per client, so many concurrent agents consume a connection each. Acceptable at single-user scale.
- **Negative:** `BaseHTTPMiddleware` is unusable for this mount. Starlette's `BaseHTTPMiddleware` buffers the response and asserts every downstream ASGI message is `http.response.body`, which crashed the app on every SSE disconnect. The auth guard is therefore a **pure ASGI middleware** (`MCPAuthMiddleware`). Any future middleware on this path must respect the same constraint. Provenance: `specs/bugs/registry.yaml` `mcp-auth-middleware-breaks-sse-stream`.

## Alternatives Considered

| Alternative | Rejected because |
|---|---|
| REST-only, no MCP | Agents would need bespoke prompting/tooling per client; MCP is the existing standard. |
| stdio transport | Requires Grimoire to be launched as a child process of the agent; incompatible with a long-running dashboard server. |
| Streamable HTTP only | The SDK's SSE transport is the mature, client-supported path; switching is a config-level change if that changes. |
| Mandatory token | Breaks the loopback quickstart; an unset token already warns loudly. |
| Full OAuth / per-agent credentials | Disproportionate for a single-user self-hosted tool with no user model (ADR-003). |
