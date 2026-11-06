# e09s02 — has-readme: README.md presence check

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 1

## Context

Every repo should have a README. Targets all repos via regex: ".*".
Simply tests for the existence of README.md. Severity: warning — informational,
doesn't block anything but good to know.


## Requirements

#### ADDED: has-readme: README.md presence check
Every repo should have a README. Targets all repos via regex: ".*".
Simply tests for the existence of README.md. Severity: warning — informational,
doesn't block anything but good to know.


## Acceptance Criteria

```gherkin
Feature: has-readme: README.md presence check
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When has-readme: README.md presence check is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — has-readme: README.md presence check
   → verify: `test -f data/checks/has-readme.yaml`

## Verification

Run runnable verify commands:
```bash
test -f data/checks/has-readme.yaml
```
