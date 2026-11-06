# e06s03 — Dashboard page with sortable repo matrix

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 5

## Context

GET / renders dashboard.html with RepoViewModel list. Sortable by name, health, issues, PRs, branches, workflow_failures, check_failures, last_activity. Three-tier health: error (red), warning (yellow), ok (green). Aggregate stats bar. Global warnings. Refresh button with HTMX polling.

## Requirements

#### ADDED: Dashboard page with sortable repo matrix
GET / renders dashboard.html with RepoViewModel list. Sortable by name, health, issues, PRs, branches, workflow_failures, check_failures, last_activity. Three-tier health: error (red), warning (yellow), ok (green). Aggregate stats bar. Global warnings. Refresh button with HTMX polling.

## Acceptance Criteria

```gherkin
Feature: Dashboard page with sortable repo matrix
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Dashboard page with sortable repo matrix is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Dashboard page with sortable repo matrix
   → verify: `grep -q 'dashboard.html' src/grimoire/web/router.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'dashboard.html' src/grimoire/web/router.py
```
