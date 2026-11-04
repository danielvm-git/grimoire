---
bug_id: BUG-2026-11-04T000007
status: fixed
severity: low
scope: github, web, observability, mcp
title: Dead pagination state, unreachable handler, metric label leak, empty MCP token
---

# BUG-2026-11-04T000007: Dead code and observability cleanup

## Problem

- **Actual:**
  - `_last_next_link` is written at `github/client.py:315` and declared at `465`
    but never read.
  - `except ActionConflictError` in the manual background task is unreachable
    (`actions/router.py:263-264`).
  - Prometheus per-repo/workflow label series are never removed
    (`observability/metrics.py:140-176`).
  - `mount_mcp_server` treats an empty token as “no auth” without a warning
    (`mcp/server.py:114-121`).
- **Expected:** no dead state; no unreachable handler; stale metric labels removed;
  an empty MCP token is visible in logs.

## TDD Fix Plan

1. **RED:**
   - `tests/test_github/test_client.py::test_no_last_next_link_state`.
   - `tests/test_observability/test_metrics.py::test_remove_repo_metrics`.
   - `tests/test_mcp/test_server.py::test_empty_token_warns`.
2. **GREEN:**
   - Remove `_last_next_link` and its assignment.
   - Remove the unreachable handler (or keep only the generic `except Exception`).
   - Add `remove_repo_metrics(names)` and call it from `prune_stale_data`.
   - Log a warning when the MCP endpoint mounts without a token.
3. **verify:** `uv run pytest tests/test_github/test_client.py tests/test_observability tests/test_mcp -q`

## Acceptance Criteria

- [ ] No `_last_next_link` state remains.
- [ ] No unreachable `ActionConflictError` handler remains.
- [ ] Pruned repos have their metric labels removed.
- [ ] Empty MCP token logs a warning.
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
