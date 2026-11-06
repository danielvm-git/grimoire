# e04s04 — Check result persistence

**type:** feature
**risk:** P1
**context:** e04-checks-engine
**bcps:** 2

## Context

_persist_result() creates CheckResult domain model + CheckResultRecord DB row with run_id foreign key. update_check_metrics() sets Prometheus gauges (CHECK_STATUS, CHECK_DURATION).

## Requirements

#### ADDED: Check result persistence
_persist_result() creates CheckResult domain model + CheckResultRecord DB row with run_id foreign key. update_check_metrics() sets Prometheus gauges (CHECK_STATUS, CHECK_DURATION).

## Acceptance Criteria

```gherkin
Feature: Check result persistence
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Check result persistence is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Check result persistence
   → verify: `python -c 'from grimoire.database import CheckRunRecord, CheckResultRecord'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.database import CheckRunRecord, CheckResultRecord'
```
