# e05s04 — Action scheduling

**type:** feature
**risk:** P1
**context:** e05-actions-engine
**bcps:** 2

## Context

register_actions() registers cron-scheduled actions with APScheduler. Actions without schedule are manual-only. Per-action enabled flag.

## Requirements

#### ADDED: Action scheduling
register_actions() registers cron-scheduled actions with APScheduler. Actions without schedule are manual-only. Per-action enabled flag.

## Acceptance Criteria

```gherkin
Feature: Action scheduling
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Action scheduling is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Action scheduling
   → verify: `python -c 'from grimoire.actions.scheduler import register_actions'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.actions.scheduler import register_actions'
```
