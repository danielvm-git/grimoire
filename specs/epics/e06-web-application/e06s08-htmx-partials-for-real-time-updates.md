# e06s08 — HTMX partials for real-time updates

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 3

## Context

Dashboard matrix/list partials for sort-switching. Refresh button status polling with HX-Trigger:refreshCompleted. Check/action run button status polling with HX-Trigger:checkRunCompleted/actionRunCompleted. Action run detail expansion, action output viewing, check output viewing, check results expansion. Backlog items filtered partial.

## Requirements

#### ADDED: HTMX partials for real-time updates
Dashboard matrix/list partials for sort-switching. Refresh button status polling with HX-Trigger:refreshCompleted. Check/action run button status polling with HX-Trigger:checkRunCompleted/actionRunCompleted. Action run detail expansion, action output viewing, check output viewing, check results expansion. Backlog items filtered partial.

## Acceptance Criteria

```gherkin
Feature: HTMX partials for real-time updates
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When HTMX partials for real-time updates is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — HTMX partials for real-time updates
   → verify: `grep -c 'partials/' src/grimoire/web/router.py | grep -v ':0$'`

## Verification

Run runnable verify commands:
```bash
grep -c 'partials/' src/grimoire/web/router.py | grep -v ':0$'
```
