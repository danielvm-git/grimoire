---
bug_id: BUG-2026-11-04T000004
status: fixed
severity: high
scope: workspace
title: Partial bare clone is not repaired by reset_workdir and worktree errors are swallowed
---

# BUG-2026-11-04T000004: Workspace partial-bare dead end

## Problem

- **Actual:** `reset_workdir()` clones only when `bare_dir` is absent
  (`workspace/manager.py:162-163`); it never calls `_ensure_bare_initialized()`.
  `_ensure_worktree()` catches `WorkspaceError` and returns (`manager.py:324-327`),
  so `reset_workdir()` proceeds into an invalid worktree.
- **Expected:** `reset_workdir()` repairs a partial bare clone; a failed worktree
  creation raises a typed `WorkspaceError`.

## Root Cause Analysis

- **Code path:** `workspace/manager.py:151-172` (`reset_workdir`),
  `269-288` (`_ensure_bare_initialized`), `306-327` (`_ensure_worktree`).
- **Why it fails:** readiness is inferred from `exists()`; the repair helper is only
  called from `setup`/`sync_repo`; the worktree error is swallowed.
- **Risk:** High. A crash during clone/worktree add makes checks/actions fail with
  “not a git repository” until the next setup/sync.

## TDD Fix Plan

1. **RED:** `tests/test_workspace/test_manager.py`
   - `test_reset_repairs_partial_bare` (spy on `_ensure_bare_initialized`).
   - `test_ensure_worktree_failure_propagates` (a `WorkspaceError` is raised).
2. **GREEN:**
   - `reset_workdir` calls `_ensure_bare_initialized(bare_dir)` when it exists.
   - `_ensure_worktree` raises instead of swallowing; `setup` catches per branch
     and logs so one missing branch does not abort the whole repo.
3. **verify:** `uv run pytest tests/test_workspace -q`

## Acceptance Criteria

- [ ] `reset_workdir` repairs a partial bare clone.
- [ ] A failed worktree add raises a typed error.
- [ ] `setup` still tolerates a single missing branch.
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
