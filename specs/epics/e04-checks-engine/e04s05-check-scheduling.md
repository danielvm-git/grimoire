# e04s05 — Check scheduling

**type:** feature
**risk:** P1
**context:** e04-checks-engine
**bcps:** 2

## Context

register_checks() registers cron-scheduled checks with APScheduler. Checks without schedule run on data-refresh cycle (app.py _do_refresh). Per-check enabled flag honored.

## Requirements

#### ADDED: Check scheduling
register_checks() registers cron-scheduled checks with APScheduler. Checks without schedule run on data-refresh cycle (app.py _do_refresh). Per-check enabled flag honored.

## Acceptance Criteria

```gherkin
Feature: Check scheduling
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Check scheduling is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Check scheduling
   → verify: `python -c 'from grimoire.checks.scheduler import register_checks'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.checks.scheduler import register_checks'
```
