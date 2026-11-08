# Module 8: MCP Server

Expose repository health, check definitions, results and the failing-check backlog to LLM agents over the Model Context Protocol (SSE transport), mounted inside the FastAPI app.

**Dependencies:** Module 1 (config), Module 2 (tracked repositories), Module 4 (checks engine and queries).

## 8.1 — Configuration

```yaml
mcp:
  enabled: true            # mount the endpoint (default: true)
  token: "${GRIMOIRE_MCP_TOKEN:-}"   # optional; empty/unset means no authentication
  endpoint_path: "/mcp"
```

Model: `MCPConfig` in `src/grimoire/config.py`. `app.py` calls `create_mcp_server()` then `mount_mcp_server()` when `enabled` is true.

## 8.2 — Server and authentication

**Package:** `src/grimoire/mcp/`

- `server.py` — `create_mcp_server(engine, checks, repos, workspace)` registers the five tools; `mount_mcp_server(app, mcp, endpoint_path, token)` mounts the SSE app.
- `MCPAuthMiddleware` is **pure ASGI middleware**, never `BaseHTTPMiddleware` (that class asserts on SSE stream messages and crashed the app on every client disconnect; see `mcp-auth-middleware-breaks-sse-stream` in the bug registry).
- A token is accepted as `X-MCP-Token: <token>` or `Authorization: Bearer <token>`. Comparison uses `secrets.compare_digest`. A missing or wrong token returns `401` and never reaches the SSE app.
- With no token the endpoint is mounted open and a warning is logged. DNS-rebinding protection is disabled because Grimoire is meant to be reached by hostname behind a reverse proxy.

## 8.3 — Tools

**File:** `src/grimoire/mcp/tools.py` (`MCPToolHandlers`)

| Tool | Parameters | Returns |
|---|---|---|
| `list_repositories` | none | one object per tracked repo: `full_name`, `default_branch`, `branches`, `source` |
| `list_checks` | none | one object per check: `slug`, `name`, `description`, `severity`, `targets` |
| `get_repo_checks_status` | `repo`, `refresh=False` | `overall_status` (`passing`/`failing`/`unknown`), counts, `latest_results` |
| `get_check_backlog` | `repo`, `refresh=False` | the backlog from `checks.queries.get_check_backlog`, one entry per branch |
| `run_repo_checks` | `repo`, `check_slug=None` | `executed_checks_count` and per-check `details` (`passed`, `results_count`, `error`) |

Validation, in order, for every tool that takes `repo`:

1. `validate_repo` — format `owner/name` (`[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`).
2. `require_tracked_repo` — the repo must be tracked; the error lists the tracked repos. An untracked repo never yields an empty success.
3. `validate_check_slug` (when `check_slug` is given), then lookup; an unknown slug raises `ValueError`.

`refresh=True` re-runs every check for that repo with `triggered_by="api"` and tolerates `CheckConflictError`. `run_repo_checks` reports a conflict as `error: "already running"` and a check that resolves no targets as an explanatory `error`.

## Acceptance Criteria

- [ ] All five tools are registered and callable through the MCP client session
- [ ] A request without a valid token gets `401` when a token is configured; the SSE stream survives client disconnects
- [ ] An untracked or malformed repo is rejected with a `ValueError` that names it
- [ ] `enabled: false` leaves `endpoint_path` unmounted
- [ ] `docs/user/reference/mcp.md` matches the registered tool list (`test_mcp_documentation_accuracy`)
