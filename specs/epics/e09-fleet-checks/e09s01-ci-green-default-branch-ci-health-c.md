# e09s01 — ci-green: default-branch CI health check

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 1

## Context

Check that the latest CI run on the default branch is passing. Targets
only repos with `.github/workflows/` via script targeting. Uses `gh run list`
to find failed runs. Severity: error — CI failures should block forward work.


## Requirements

#### ADDED: ci-green: default-branch CI health check
Check that the latest CI run on the default branch is passing. Targets
only repos with `.github/workflows/` via script targeting. Uses `gh run list`
to find failed runs. Severity: error — CI failures should block forward work.


## Acceptance Criteria

```gherkin
Feature: ci-green: default-branch CI health check
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When ci-green: default-branch CI health check is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — ci-green: default-branch CI health check
   → verify: `test -f data/checks/ci-green.yaml`

## Verification

Run runnable verify commands:
```bash
test -f data/checks/ci-green.yaml
```
