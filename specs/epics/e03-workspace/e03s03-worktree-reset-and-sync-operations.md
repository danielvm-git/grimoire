# e03s03 — Worktree reset and sync operations

**type:** feature
**risk:** P1
**context:** e03-workspace
**bcps:** 3

## Context

reset_workdir(): checkout branch, reset --hard origin/{branch}, clean -fdx. sync_repo(): fetch origin, reset all existing worktrees. sync_all(): concurrent fetch+reset across all repos with Semaphore(10). safe.bareRepository=all for git >=2.38.

## Requirements

#### ADDED: Worktree reset and sync operations
reset_workdir(): checkout branch, reset --hard origin/{branch}, clean -fdx. sync_repo(): fetch origin, reset all existing worktrees. sync_all(): concurrent fetch+reset across all repos with Semaphore(10). safe.bareRepository=all for git >=2.38.

## Acceptance Criteria

```gherkin
Feature: Worktree reset and sync operations
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Worktree reset and sync operations is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Worktree reset and sync operations
   → verify: `grep -q 'reset --hard' src/grimoire/workspace/manager.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'reset --hard' src/grimoire/workspace/manager.py
```
