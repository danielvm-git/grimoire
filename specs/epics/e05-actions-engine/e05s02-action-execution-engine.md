# e05s02 — Action execution engine

**type:** feature
**risk:** P1
**context:** e05-actions-engine
**bcps:** 6

## Context

run_action() creates ActionRunRecord, resolves targets, executes sequentially per repo+branch. sync_repo() + reset_workdir() before each execution. Global actions (targets=None) run once in workspace_dir with full env. Concurrent run guard via DB check. ActionProgress tracks progress. Timeout 600s, output cap 64KB.

## Requirements

#### ADDED: Action execution engine
run_action() creates ActionRunRecord, resolves targets, executes sequentially per repo+branch. sync_repo() + reset_workdir() before each execution. Global actions (targets=None) run once in workspace_dir with full env. Concurrent run guard via DB check. ActionProgress tracks progress. Timeout 600s, output cap 64KB.

## Acceptance Criteria

```gherkin
Feature: Action execution engine
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Action execution engine is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Action execution engine
   → verify: `python -c 'from grimoire.actions.engine import run_action, is_action_running, ActionConflictError'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.actions.engine import run_action, is_action_running, ActionConflictError'
```
