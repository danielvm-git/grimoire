# e04s06 — Check REST API

**type:** feature
**risk:** P1
**context:** e04-checks-engine
**bcps:** 4

## Context

GET /api/checks → list definitions. GET /api/checks/{slug}/results → latest per-repo+branch. GET /api/checks/{slug}/runs → run history. GET /api/checks/{slug}/runs/{id} → run detail with per-repo results. POST /api/checks/{slug}/run → trigger (409 if running). POST /api/checks/{slug}/toggle → enable/disable with DB persistence. GET /api/checks/{slug}/status → running state.

## Requirements

#### ADDED: Check REST API
GET /api/checks → list definitions. GET /api/checks/{slug}/results → latest per-repo+branch. GET /api/checks/{slug}/runs → run history. GET /api/checks/{slug}/runs/{id} → run detail with per-repo results. POST /api/checks/{slug}/run → trigger (409 if running). POST /api/checks/{slug}/toggle → enable/disable with DB persistence. GET /api/checks/{slug}/status → running state.

## Acceptance Criteria

```gherkin
Feature: Check REST API
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Check REST API is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Check REST API
   → verify: `curl -s http://localhost:8000/api/checks | python -c 'import json,sys; d=json.load(sys.stdin); assert isinstance(d, list)'`

## Verification

Run runnable verify commands:
```bash
curl -s http://localhost:8000/api/checks | python -c 'import json,sys; d=json.load(sys.stdin); assert isinstance(d, list)'
```
