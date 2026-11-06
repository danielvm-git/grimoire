# e06s04 — Repository detail page

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 3

## Context

GET /repo/{owner}/{name} renders repository.html. Per-branch workflow list, check results, issue/PR counts, warnings, last commit, branch list. Not-found page for un tracked repos.

## Requirements

#### ADDED: Repository detail page
GET /repo/{owner}/{name} renders repository.html. Per-branch workflow list, check results, issue/PR counts, warnings, last commit, branch list. Not-found page for un tracked repos.

## Acceptance Criteria

```gherkin
Feature: Repository detail page
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Repository detail page is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Repository detail page
   → verify: `grep -q 'repository.html' src/grimoire/web/router.py`

## Verification

Run runnable verify commands:
```bash
grep -q 'repository.html' src/grimoire/web/router.py
```
