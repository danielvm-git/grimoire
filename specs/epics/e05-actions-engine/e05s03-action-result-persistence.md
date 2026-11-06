# e05s03 — Action result persistence

**type:** feature
**risk:** P1
**context:** e05-actions-engine
**bcps:** 2

## Context

ActionRunRepoRecord per repo+branch result with run_id foreign key. ActionRunRecord status: running → completed. update_action_metrics() sets ACTION_DURATION histogram.

## Requirements

#### ADDED: Action result persistence
ActionRunRepoRecord per repo+branch result with run_id foreign key. ActionRunRecord status: running → completed. update_action_metrics() sets ACTION_DURATION histogram.

## Acceptance Criteria

```gherkin
Feature: Action result persistence
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Action result persistence is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Action result persistence
   → verify: `python -c 'from grimoire.database import ActionRunRecord, ActionRunRepoRecord'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.database import ActionRunRecord, ActionRunRepoRecord'
```
