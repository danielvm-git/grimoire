# e06s07 — Backlog page with weighted scoring

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 6

## Context

GET /backlog renders prioritized problem list. WSJF-inspired scoring: category base weights × repository multipliers × workflow weights. Five categories (failing_workflow, failing_check_error, failing_check_warning, stale_pr, stale_issue). Four priority tiers (critical/high/medium/low). Filter by category, repo, min_score, search. Group by repo or type. Markdown export. Configurable weights save-back to config.yaml.

## Requirements

#### ADDED: Backlog page with weighted scoring
GET /backlog renders prioritized problem list. WSJF-inspired scoring: category base weights × repository multipliers × workflow weights. Five categories (failing_workflow, failing_check_error, failing_check_warning, stale_pr, stale_issue). Four priority tiers (critical/high/medium/low). Filter by category, repo, min_score, search. Group by repo or type. Markdown export. Configurable weights save-back to config.yaml.

## Acceptance Criteria

```gherkin
Feature: Backlog page with weighted scoring
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Backlog page with weighted scoring is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Backlog page with weighted scoring
   → verify: `grep -q 'backlog.html' src/grimoire/web/router.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'backlog.html' src/grimoire/web/router.py
```
