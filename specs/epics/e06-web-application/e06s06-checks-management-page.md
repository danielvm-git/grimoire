# e06s06 — Checks management page

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 4

## Context

GET /checks renders checks.html with CheckViewModel list. Per-check stats (pass/fail/warn/last_run). Severity-aware display (error vs warning). Inline results expansion via HTMX grouped by run. Individual result output viewing. Run button with progress polling.

## Requirements

#### ADDED: Checks management page
GET /checks renders checks.html with CheckViewModel list. Per-check stats (pass/fail/warn/last_run). Severity-aware display (error vs warning). Inline results expansion via HTMX grouped by run. Individual result output viewing. Run button with progress polling.

## Acceptance Criteria

```gherkin
Feature: Checks management page
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Checks management page is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Checks management page
   → verify: `grep -q 'checks.html' src/grimoire/web/router.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'checks.html' src/grimoire/web/router.py
```
