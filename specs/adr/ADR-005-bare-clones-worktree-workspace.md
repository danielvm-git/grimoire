# ADR-005: Git Bare Clones and Ephemeral Worktrees for Script Execution

## Status
Accepted

## Context
Checks and actions must run local bash scripts against specific branches across dozens of repositories. Creating full individual git clones per branch causes excessive disk usage and network overhead.

## Decision
Implement `WorkspaceManager` using a bare git clone (`git clone --bare`) per repository stored under `/workspace/{owner}/{name}.git`, and dynamically create lightweight git worktrees (`git worktree add`) for each target branch.

## Consequences
- **Positive:** Multi-branch checkouts share the underlying object store, saving gigabytes of disk space and reducing network transfer to incremental fetch.
- **Negative:** Requires managing worktree cleanup and handling stale lockfiles if the process is terminated abruptly.

## Stress-Testing Evidence (grill-me)
- **Challenge:** What happens if a worktree checkout is aborted mid-execution?
- **Resolution:** Worktree reset logic runs `checkout → reset --hard origin/{branch} → clean -fdx` before every execution, and `git worktree prune` cleans orphaned paths on startup. Verified in `tests/test_workspace/test_manager.py`.
