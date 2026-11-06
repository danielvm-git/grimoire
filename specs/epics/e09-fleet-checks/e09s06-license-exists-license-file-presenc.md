# e09s06 — license-exists: LICENSE file presence

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 1

## Context

Verify every repo has a LICENSE file. Targets all repos via regex: ".*".
Severity: warning — licensing matters but isn't an emergency.


## Requirements

#### ADDED: license-exists: LICENSE file presence
Verify every repo has a LICENSE file. Targets all repos via regex: ".*".
Severity: warning — licensing matters but isn't an emergency.


## Acceptance Criteria

```gherkin
Feature: license-exists: LICENSE file presence
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When license-exists: LICENSE file presence is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — license-exists: LICENSE file presence
   → verify: `test -f data/checks/license-exists.yaml`

## Verification

Run runnable verify commands:
```bash
test -f data/checks/license-exists.yaml
```
