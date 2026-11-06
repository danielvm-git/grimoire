# e03s04 — Environment variable injection for subprocesses

**type:** feature
**risk:** P1
**context:** e03-workspace
**bcps:** 1

## Context

get_env() exports GH_TOKEN, GITHUB_TOKEN, git identity vars, GIT_SSH_COMMAND. target_env() adds per-invocation REPO_OWNER, REPO_NAME, REPO_FULL_NAME, BRANCH, DEFAULT_BRANCH.

## Requirements

#### ADDED: Environment variable injection for subprocesses
get_env() exports GH_TOKEN, GITHUB_TOKEN, git identity vars, GIT_SSH_COMMAND. target_env() adds per-invocation REPO_OWNER, REPO_NAME, REPO_FULL_NAME, BRANCH, DEFAULT_BRANCH.

## Acceptance Criteria

```gherkin
Feature: Environment variable injection for subprocesses
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Environment variable injection for subprocesses is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Environment variable injection for subprocesses
   → verify: `grep -q 'GH_TOKEN' src/grimoire/workspace/manager.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'GH_TOKEN' src/grimoire/workspace/manager.py
```
