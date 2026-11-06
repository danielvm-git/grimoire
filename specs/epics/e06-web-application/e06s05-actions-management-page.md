# e06s05 — Actions management page

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 4

## Context

GET /actions renders actions.html with ActionViewModel list. Per-action stats from DB (pass/fail/last_run). Inline run history expansion via HTMX. Individual run output viewing. Run button with progress polling.

## Requirements

#### ADDED: Actions management page
GET /actions renders actions.html with ActionViewModel list. Per-action stats from DB (pass/fail/last_run). Inline run history expansion via HTMX. Individual run output viewing. Run button with progress polling.

## Acceptance Criteria

```gherkin
Feature: Actions management page
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Actions management page is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Actions management page
   → verify: `grep -q 'actions.html' src/grimoire/web/router.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'actions.html' src/grimoire/web/router.py
```
