---
bug_id: BUG-2026-11-04T000005
status: fixed
severity: high
scope: checks, actions
title: Subprocess survives task cancellation and becomes an orphan
---

# BUG-2026-11-04T000005: Subprocess cancellation leak

## Problem

- **Actual:** the engines only `kill()` the child on `asyncio.TimeoutError`
  (`checks/engine.py:165-170`; `actions/engine.py:268-273`). A `CancelledError`
  (shutdown/task cancellation) propagates through a `finally` that only unlinks the
  temp script, leaving the child running.
- **Expected:** every exit path kills and reaps the child.

## Root Cause Analysis

- **Code path:** `checks/engine.py:132-177`, `actions/engine.py:254-281`,
  `targeting.py:115-144`, `script.py:102-141`.
- **Why it fails:** cancellation is a `BaseException`; the timeout handler does not
  see it, and the `finally` has no process cleanup.
- **Risk:** High. Orphan processes survive app shutdown and can hold worktree locks.

## TDD Fix Plan

1. **RED:** `tests/test_script.py::test_cancelled_run_kills_child`
   - Start a script that writes its PID to a file and sleeps; cancel the task;
     assert the PID is gone.
2. **GREEN:** add `_terminate_process(proc)` (kill + `await asyncio.shield(proc.wait())`)
   and call it from the `finally` of `run_check`, `_execute_action`,
   `_execute_global_action`, and `_script_matches`.
3. **verify:** `uv run pytest tests/test_script.py tests/test_checks/test_engine.py -q`

## Acceptance Criteria

- [ ] Cancelling a check/action kills and reaps its child.
- [ ] Timeout behavior is unchanged.
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
