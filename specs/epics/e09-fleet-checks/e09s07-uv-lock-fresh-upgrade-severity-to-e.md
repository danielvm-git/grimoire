# e09s07 — uv-lock-fresh: upgrade severity to error

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 1

## Context

Existing check (uv-lock-fresh.yaml) is severity: warning. Upgrade to
severity: error so stale lockfiles show as red on the dashboard and get
higher backlog priority. No script changes needed.


## Requirements

#### ADDED: uv-lock-fresh: upgrade severity to error
Existing check (uv-lock-fresh.yaml) is severity: warning. Upgrade to
severity: error so stale lockfiles show as red on the dashboard and get
higher backlog priority. No script changes needed.


## Acceptance Criteria

```gherkin
Feature: uv-lock-fresh: upgrade severity to error
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When uv-lock-fresh: upgrade severity to error is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — uv-lock-fresh: upgrade severity to error
   → verify: `grep -q 'severity: error' data/checks/uv-lock-fresh.yaml`

## Verification

Run runnable verify commands:
```bash
grep -q 'severity: error' data/checks/uv-lock-fresh.yaml
```
