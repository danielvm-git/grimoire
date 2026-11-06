# Ubiquitous Language — Grimoire

Domain model vocabulary extracted and formalized across `grimoire` packages (`github`, `checks`, `actions`, `web`, `workspace`, `observability`).

## Core Domain Terms

### 1. TrackedRepository
A GitHub repository explicitly configured or dynamically resolved via GitHub team memberships for continuous monitoring.

### 2. RepositoryStats
An in-memory and SQLite-cached snapshot of operational repository metrics:
- Open issues vs stale issues (default threshold: 365 days without comment)
- Open pull requests vs stale pull requests (default threshold: 30 days without activity)
- CI workflow conclusions on default and tracked branches
- Latest commit metadata and active branch counts

### 3. Check & CheckSeverity
A **Check** is an idempotent, read-only script executed inside an isolated git worktree against targeted repos/branches.
- **`severity: error`**: Failures turn the repository health status red / failed.
- **`severity: warning`**: Failures indicate technical debt or warnings; repo health remains green / passing.

### 4. Action
An **Action** is a stateful, sequential script executed inside an isolated git worktree with write permissions (e.g. running refactors, updating files, triggering PRs). Actions do not run concurrently on the same repository.

### 5. WorkspaceManager
A local filesystem abstraction utilizing a single bare clone per tracked repository and checking out ephemeral git worktrees for check/action script runs. Eliminates multi-gigabyte repository duplication.

### 6. BacklogScore
A weighted WSJF calculation aggregating issue staleness, PR staleness, broken workflows, and error-severity check failures into a single actionable priority rank for developers.

### 7. Lifespan
The asynchronous initialization cycle in `app.py` executing config resolution, DB table migrations, scheduler startup, and initial repository discovery.
