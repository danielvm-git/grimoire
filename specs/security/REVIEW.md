# Security Review — e12 MCP Server & Query Layer

- **Date**: 2026-11-06
- **Epic**: e12-mcp-server
- **Release**: v0.12.0
- **Status**: PASSED (with 1 documented LOW/MEDIUM observation)
- **Scope**: `src/grimoire/mcp/server.py`, `src/grimoire/mcp/tools.py`, `src/grimoire/checks/queries.py`, MCP mount in `src/grimoire/app.py`
- **Threat model**: `specs/security/epics/e12/THREAT_MODEL.md`

## Summary

A security analysis of the e12 changes was performed across the FastMCP server, the SSE
transport mount, the bearer-token auth middleware, and the MCP tool handlers.

## Findings

- **Authentication on `/mcp`** — PASS. `MCPAuthMiddleware` accepts either `X-MCP-Token` or
  `Authorization: Bearer <token>` and compares with `secrets.compare_digest` (constant-time,
  no timing oracle). Missing or wrong token returns 401 before the SSE app is reached.
  When `mcp.token` is empty the endpoint mounts unauthenticated and emits an explicit
  startup warning (`server.py:127`) rather than failing silently.
- **Injection / command execution** — PASS. `run_repo_checks` and `get_repo_checks_status`
  validate inputs with anchored regexes (`^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$` for repos,
  `^[a-zA-Z0-9_-]+$` for check slugs) before any database or subprocess invocation.
  Check execution reuses the existing `checks/engine` path, which does not interpolate
  user input into a shell string.
- **DoS / concurrency** — PASS. `run_check_for_all_targets` surfaces `CheckConflictError`
  on concurrent runs instead of spawning unbounded subprocesses.
- **Information disclosure** — PASS. Check output is truncated at the 64 KB cap consistent
  with the rest of the engine; no token or config values are returned by any tool.
- **Secrets exposure** — PASS. No credentials committed. `mcp.token` resolves through the
  standard config/env-var layer.
- **SQL injection** — PASS. All query-layer access uses SQLModel/parameterized statements.

## Observation (accepted, not blocking)

- `mount_mcp_server` sets `TransportSecuritySettings(enable_dns_rebinding_protection=False)`.
  This is required for self-hosted deployments reached by IP or reverse proxy, but it means
  a browser on the same network could reach `/mcp` via DNS rebinding **if no token is
  configured**. Mitigation is operational: set `mcp.token`. Documented in the user docs.
  Severity LOW when a token is set; MEDIUM only in the tokenless configuration, which is
  already warned about at startup.

## Conclusion

Zero unresolved HIGH or CRITICAL severity findings. Constant-time token comparison landed in
`631e614`. Clean for merge to main.
