# e02s06 — Concurrent refresh with Semaphore(10)

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 2

## Context

refresh_all_stats() resolves repos, fetches stats concurrently with asyncio.Semaphore(10), persists to DB. RefreshProgress tracks completed/total. is_refresh_running() and get_refresh_progress() for polling.

## Requirements

#### ADDED: Concurrent refresh with Semaphore(10)
refresh_all_stats() resolves repos, fetches stats concurrently with asyncio.Semaphore(10), persists to DB. RefreshProgress tracks completed/total. is_refresh_running() and get_refresh_progress() for polling.

## Acceptance Criteria

```gherkin
Feature: Concurrent refresh with Semaphore(10)
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Concurrent refresh with Semaphore(10) is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Concurrent refresh with Semaphore(10)
   → verify: `python -c 'from grimoire.github.service import refresh_all_stats, is_refresh_running'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.github.service import refresh_all_stats, is_refresh_running'
```
