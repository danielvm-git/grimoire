# e02s07 — DB persistence: save, load, prune

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 4

## Context

save_stats_to_db() clears old cached data per repo, writes fresh CachedRepository, CachedIssue, CachedPullRequest, CachedWorkflowStatus. load_stats_from_db() reconstructs TrackedRepository + RepositoryStats from DB. prune_removed_repos() and prune_stale_data() clean up removed repos and excluded workflows.

## Requirements

#### ADDED: DB persistence: save, load, prune
save_stats_to_db() clears old cached data per repo, writes fresh CachedRepository, CachedIssue, CachedPullRequest, CachedWorkflowStatus. load_stats_from_db() reconstructs TrackedRepository + RepositoryStats from DB. prune_removed_repos() and prune_stale_data() clean up removed repos and excluded workflows.

## Acceptance Criteria

```gherkin
Feature: DB persistence: save, load, prune
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When DB persistence: save, load, prune is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — DB persistence: save, load, prune
   → verify: `python -c 'from grimoire.github.service import save_stats_to_db, load_stats_from_db, prune_removed_repos'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.github.service import save_stats_to_db, load_stats_from_db, prune_removed_repos'
```
