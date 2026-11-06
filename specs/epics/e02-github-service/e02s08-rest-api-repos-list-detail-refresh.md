# e02s08 — REST API: repos list, detail, refresh

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 3

## Context

GET /api/repos → RepoListResponse with summaries. GET /api/repos/{owner}/{name} → RepoDetailResponse with workflows. POST /api/refresh → trigger background refresh. GET /api/refresh/status → progress polling. In-memory cache updated by refresh callback.

## Requirements

#### ADDED: REST API: repos list, detail, refresh
GET /api/repos → RepoListResponse with summaries. GET /api/repos/{owner}/{name} → RepoDetailResponse with workflows. POST /api/refresh → trigger background refresh. GET /api/refresh/status → progress polling. In-memory cache updated by refresh callback.

## Acceptance Criteria

```gherkin
Feature: REST API: repos list, detail, refresh
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When REST API: repos list, detail, refresh is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — REST API: repos list, detail, refresh
   → verify: `curl -s http://localhost:8000/api/repos | python -c 'import json,sys; d=json.load(sys.stdin); assert "repositories" in d'`

## Verification

Run runnable verify commands:
```bash
curl -s http://localhost:8000/api/repos | python -c 'import json,sys; d=json.load(sys.stdin); assert "repositories" in d'
```
