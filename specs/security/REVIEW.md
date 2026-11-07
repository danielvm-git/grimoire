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
  The guard is a **pure ASGI middleware**, not a `BaseHTTPMiddleware`: the latter buffers the
  response and asserted on every SSE client disconnect, crashing the ASGI app
  (`specs/bugs/registry.yaml` `mcp-auth-middleware-breaks-sse-stream`, fixed in `a8dadc2`).
  When `mcp.token` is empty the endpoint mounts unauthenticated and emits an explicit
  startup warning (`server.py`) rather than failing silently.
- **Injection / command execution** — PASS. `run_repo_checks` and `get_repo_checks_status`
  validate inputs with anchored regexes (`^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$` for repos,
  `^[a-zA-Z0-9_-]+$` for check slugs) before any database or subprocess invocation, and
  `require_tracked_repo` rejects repositories Grimoire does not track. Check execution reuses
  the existing `checks/engine` path, which does not interpolate user input into a shell string.
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
`631e614`; the streaming-safe pure ASGI middleware landed in `a8dadc2` during the e12
post-epic review. Clean for merge to main.

## Post-epic review (2026-11-06)

Re-reviewed as part of the e12 post-epic pass. One security-relevant defect was found and
fixed: the `BaseHTTPMiddleware` auth guard broke the SSE stream on every client disconnect
(unhandled ASGI exception per reconnect). No credential handling, validation or trust-boundary
change was introduced by the review fixes. Findings: `specs/bugs/registry.yaml`
`mcp-auth-middleware-breaks-sse-stream`, `mcp-tools-report-vacuous-success`,
`mcp-list-checks-missing-targets`. Decision record: `specs/adr/ADR-006-mcp-server-sse-token-auth.md`.

## Branch review (2026-11-07) — `fix/sqlite-database-locked`

- **Scope**: `src/grimoire/database.py`, `src/grimoire/db_exec.py`,
  `src/grimoire/github/client.py`, `src/grimoire/github/service.py`
  (diff `main...HEAD`)
- **Threat-model delta**: none. No auth boundary, credential path, or trust-boundary change.

| Area | Verdict | Notes |
|---|---|---|
| SQL injection (CWE-89) | PASS | The only new SQL fragments are `PRAGMA busy_timeout={int(busy_timeout_ms)}`, `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`. The interpolation is an `int()`-cast value supplied by the process (never by config, HTTP, MCP, or repo/branch names); provenance is developer-authored with a type-enforced integer, so no attacker-reachable string reaches the statement. All application queries remain bound-parameter or ORM-built. |
| Failure masking / fail-open (CWE-390) | PASS | `_save_etag_safely` and `_load_etag_safely` swallow a `sqlalchemy.exc.OperationalError` **only** when `is_lock_error()` matches the SQLITE_BUSY family; every other `OperationalError` (schema errors, corruption, read-only database) is re-raised. No authentication or authorization decision depends on the ETag cache. |
| Denial of service (CWE-400) | PASS | `retry_on_lock` is bounded (`attempts` + fixed backoff tuple) and sleeps asynchronously, so it cannot busy-spin the event loop or retry indefinitely. Worst case adds ~1.3 s of latency to a cache write. |
| Sensitive data exposure (CWE-532) | PASS | Lock warnings log the GitHub API path (`url_key`: path + pagination/branch params) and the attempt counter — no token, no response body, no SQL parameters. |
| Secret leakage via VCS (CWE-552) | PASS (improved) | `.gitignore` now covers `grimoire.db*`, so the WAL sidecars (`-wal`, `-shm`) cannot be committed. Sidecars hold only the same data as the database file; no new exposure class, and the user docs now tell operators to copy them with the DB for backups. |

**Findings ≥ confidence 8**: none. **Conclusion**: clean for merge to main.
