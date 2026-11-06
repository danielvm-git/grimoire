---
bug_id: BUG-2026-08-10T161500
status: open
severity: high
scope: config
title: Unset optional env placeholder in config.yaml crashes app boot
---

# BUG-2026-08-10T161500: Unset optional env placeholder in config.yaml crashes app boot

## Problem

- **Actual behavior:** After commit `b4b3568` (feat(config): configure mcp section with env var placeholder) was deployed, the application never boots. The site serves the platform placeholder page instead of the Grimoire dashboard. Production outage since 2026-08-04 16:07 UTC.
- **Expected behavior:** The application must always boot from a valid config. An optional, unset token must not prevent startup — it should degrade gracefully (e.g. MCP mounted unauthenticated, or MCP disabled), while required settings still fail fast.
- **How to reproduce:** `unset GRIMOIRE_MCP_TOKEN && python -c "from grimoire.config import load_config; load_config()"` with a config containing `mcp.token: "${GRIMOIRE_MCP_TOKEN}"` → `ValueError: Environment variable 'GRIMOIRE_MCP_TOKEN' is referenced in config but not set`.

## Root Cause Analysis

- **Code path:** `load_config()` parses `config.yaml`, then calls `resolve_env_vars()` on the raw mapping before schema validation. `resolve_env_vars` matches any string of the exact shape `${VAR}` and calls `os.environ.get(VAR)`; if the variable is unset it raises `ValueError`, which aborts the whole load.
- **Why it fails:** `mcp.token` is an **optional** setting (`MCPConfig.token: str | None = None`), and the app already handles `token=None` (mounts the MCP SSE app without auth middleware). But `config.yaml` referenced it with the strict `${GRIMOIRE_MCP_TOKEN}` form, and the deployed environment does not define that variable. The strict raise — a deliberate fail-fast contract for **required** settings such as `github.token` — was triggered by an **optional** setting.
- **Contributing factors:** the strictness is a tested contract (`resolve_env_vars("${DEFINITELY_NOT_SET_12345}")` must raise), so weakening it globally would silently mask typos in required vars. The fix must add an explicit *optional* reference form instead.

**Second root cause (discovered during rollback) — platform deploy health race:** the repo's committed `bigbase.yaml` health check uses defaults (path `/health`, interval 2s, max retries 5 → ~8s window) probed immediately while the app starts. Grimoire's cold start (uv sync at build + heavy imports: mcp, opentelemetry, fastapi) binds port 10002 in ~40s, so every deploy is marked failed with "connection refused" even though the app runs. Fixed by tuning `health_check` in `bigbase.yaml` (interval 5s, max_retries 36 → ~3min window).
- **Risk level:** Low. Change is additive (new opt-out syntax), preserves existing strict behavior for plain `${VAR}`.

## Security impact

NONE — no exploit path identified. The failure is a startup crash from a missing environment variable; no data exposure, injection, or auth bypass. (Note: with `token` unset/empty the MCP endpoint mounts without auth, same as the last known-good deploy `83316b47`.)

## TDD Fix Plan

1. **RED:** Extend env-var resolution tests in `tests/test_config.py`:
   - `resolve_env_vars("${OPTIONAL_UNSET_VAR:-}") == ""` (no raise, empty default)
   - `resolve_env_vars("${OPTIONAL_UNSET_VAR:-fallback}") == "fallback"`
   - `${OPTIONAL_VAR:-x}` still resolves to the environment value when the variable **is** set
   - plain `${REQUIRED_UNSET_VAR}` still raises (strictness preserved)
   **GREEN:** Extend the env-var pattern in the config module to support `${VAR:-default}` (default may be empty); return the default when the variable is unset/empty instead of raising.
   **verify:** `uv run pytest tests/test_config.py -q`

2. **RED:** Add an integration test that a config file containing `mcp.token: "${GRIMOIRE_MCP_TOKEN:-}"` loads successfully with the token empty/None when the variable is unset.
   **GREEN:** Update `config.yaml` to use the optional form for `mcp.token`.
   **verify:** `uv run pytest tests/test_config.py -q` + `uv run python -c "from grimoire.app import create_app; create_app()"` with the variable unset.

**REFACTOR:** none expected — the change is contained to one resolver function plus one config line.

## Acceptance Criteria

- [ ] App boots with `GRIMOIRE_MCP_TOKEN` unset and the `mcp` section present in `config.yaml`
- [ ] Plain `${REQUIRED_VAR}` still raises for unset variables (existing contract intact)
- [ ] New tests pass; existing tests still pass
- [ ] `just check` green
- [ ] Deployed site serves the dashboard (verified after landing via the pipeline)

## Resolution

<!-- filled in by validate-fix -->

- **Fixed by:** PR #28 (rollback — revert `b4b3568`) + PR #29 (`fix(config): support optional env placeholder default for mcp token`, `fix(deploy): widen health check window for slow python cold start`).
- **Verification:** `just check` green (455 passed, 6 new tests). Deployed commit `bc0ded12` status=running on the platform; site serves the Grimoire dashboard; `/health` returns `{"status":"ok","version":"0.10.2"}`.
- **Note (pre-existing, not caused by this incident):** `/api/*` paths (e.g. `/api/repos`, `/api/backlog/export`) are intercepted by the BigBase platform because the deploy action passes no `passthrough_paths`; the dashboard itself (server-rendered pages + HTMX partials) works.
