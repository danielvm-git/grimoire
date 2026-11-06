# e03s01 — Bare clone + worktree layout

**type:** feature
**risk:** P1
**context:** e03-workspace
**bcps:** 5

## Context

WorkspaceManager clones repos as bare clones ({workspace_dir}/{owner}/{repo}/.bare/), creates worktrees per branch ({workspace_dir}/{owner}/{repo}/{branch}/). Fetch refspec configured to populate refs/remotes/origin/*. Per-repo asyncio.Lock prevents race conditions during concurrent worktree creation.

## Requirements

#### ADDED: Bare clone + worktree layout
WorkspaceManager clones repos as bare clones ({workspace_dir}/{owner}/{repo}/.bare/), creates worktrees per branch ({workspace_dir}/{owner}/{repo}/{branch}/). Fetch refspec configured to populate refs/remotes/origin/*. Per-repo asyncio.Lock prevents race conditions during concurrent worktree creation.

## Acceptance Criteria

```gherkin
Feature: Bare clone + worktree layout
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Bare clone + worktree layout is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Bare clone + worktree layout
   → verify: `python -c 'from grimoire.workspace.manager import WorkspaceManager'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.workspace.manager import WorkspaceManager'
```
