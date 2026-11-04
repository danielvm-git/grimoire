---
bug_id: BUG-2026-11-04T000001
status: fixed
severity: critical
scope: checks
title: Check admission guard is bypassed by cron, refresh and MCP; memory flags leak
---

# BUG-2026-11-04T000001: Check admission guard bypass

## Problem

- **Actual:** `try_start_check()` is called only by the REST endpoint and the HTMX
  partial. Cron (`checks/scheduler.py:46-53`), refresh default checks (`app.py:267-280`)
  and MCP (`mcp/tools.py:88-96,109-117,135-143`) call `run_check_for_all_targets()`
  directly. Two runs for the same slug execute; the first finisher pops the shared
  `_running_checks` entry. `_check_lock` is dead code.
- **Expected:** every entry point acquires the same admission guard; at most one run
  per slug executes; a dropped background task's memory flag expires.

## Root Cause Analysis

- **Code path:** `checks/engine.py:49-80` (`_running_checks`, `_check_lock`,
  `try_start_check`), `227-301` (`run_check_for_all_targets`), `checks/router.py:276`,
  `web/router.py:1297`.
- **Why it fails:** admission is enforced at the HTTP layer, not inside the engine.
  The engine's `finally` unconditionally pops the slug (`checks/engine.py:301`).
- **Risk:** Critical. Duplicate worktree execution, duplicate result rows, idle UI
  while a run is active.

## TDD Fix Plan

1. **RED:** `tests/test_checks/test_engine.py`
   - `test_two_entry_points_run_once` (cron + MCP, one script execution).
   - `test_prepare_check_run_conflict` (second admission raises).
   - `test_stale_memory_flag_expires` (an old entry is ignored/expired).
2. **GREEN:**
   - Add `CheckConflictError` and `prepare_check_run(check, engine, triggered_by)`
     under `_check_lock`, checking memory + DB `queued|running`.
   - Make `run_check_for_all_targets()` call `prepare_check_run()` when `run_id is None`.
   - Add `expires_at` to `CheckProgress`; `is_check_running()` expires old entries.
   - Update `checks/router.py:260-317` and `web/router.py:1257-1332` to use
     `prepare_check_run()` and map `CheckConflictError` to 409.
   - Remove the dead `_check_lock` or use it in `prepare_check_run`.
3. **verify:** `uv run pytest tests/test_checks -q`

## Acceptance Criteria

- [ ] Cron + MCP + manual triggers run a check at most once concurrently.
- [ ] A second admission returns 409.
- [ ] A dropped background task's memory flag expires after the lease window.
- [ ] `_check_lock` is used (no dead code).
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
