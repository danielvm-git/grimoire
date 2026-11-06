# e06s02 — Loading page with progress polling

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 2

## Context

GET / renders loading.html when no cache + refresh running. DaisyUI progress bar. HTMX polls GET /partials/loading-status every 2s. HX-Redirect to / on completion. Non-blocking startup via asyncio.create_task().

## Requirements

#### ADDED: Loading page with progress polling
GET / renders loading.html when no cache + refresh running. DaisyUI progress bar. HTMX polls GET /partials/loading-status every 2s. HX-Redirect to / on completion. Non-blocking startup via asyncio.create_task().

## Acceptance Criteria

```gherkin
Feature: Loading page with progress polling
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Loading page with progress polling is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Loading page with progress polling
   → verify: `grep -q 'loading.html' src/grimoire/web/router.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'loading.html' src/grimoire/web/router.py
```
