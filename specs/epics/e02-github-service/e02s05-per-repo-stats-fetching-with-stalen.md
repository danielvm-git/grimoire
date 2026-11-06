# e02s05 — Per-repo stats fetching with staleness detection

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 5

## Context

fetch_repository_stats() returns RepositoryStats: open/stale issues, open/stale PRs, workflow statuses, branch count, last commit. Staleness: issues >365d no comment, PRs >30d no push/comment. Workflow include/exclude via fnmatch. 304 fallback to previous values.

## Requirements

#### ADDED: Per-repo stats fetching with staleness detection
fetch_repository_stats() returns RepositoryStats: open/stale issues, open/stale PRs, workflow statuses, branch count, last commit. Staleness: issues >365d no comment, PRs >30d no push/comment. Workflow include/exclude via fnmatch. 304 fallback to previous values.

## Acceptance Criteria

```gherkin
Feature: Per-repo stats fetching with staleness detection
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Per-repo stats fetching with staleness detection is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Per-repo stats fetching with staleness detection
   → verify: `python -c 'from grimoire.github.service import fetch_repository_stats'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.github.service import fetch_repository_stats'
```
