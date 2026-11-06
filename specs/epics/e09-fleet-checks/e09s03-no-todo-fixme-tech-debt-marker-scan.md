# e09s03 — no-todo-fixme: tech debt marker scan

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 1

## Context

Grep for TODO, FIXME, HACK markers in source files. Targets all repos via
regex: ".*". Skips vendor directories, node_modules, .git. Severity: warning —
visibility into tech debt accumulation.


## Requirements

#### ADDED: no-todo-fixme: tech debt marker scan
Grep for TODO, FIXME, HACK markers in source files. Targets all repos via
regex: ".*". Skips vendor directories, node_modules, .git. Severity: warning —
visibility into tech debt accumulation.


## Acceptance Criteria

```gherkin
Feature: no-todo-fixme: tech debt marker scan
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When no-todo-fixme: tech debt marker scan is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — no-todo-fixme: tech debt marker scan
   → verify: `test -f data/checks/no-todo-fixme.yaml`

## Verification

Run runnable verify commands:
```bash
test -f data/checks/no-todo-fixme.yaml
```
