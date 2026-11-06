# e05s05 — Action REST API

**type:** feature
**risk:** P1
**context:** e05-actions-engine
**bcps:** 4

## Context

GET /api/actions → list definitions with target counts. GET /api/actions/{slug}/runs → run history. GET /api/actions/{slug}/runs/{id} → run detail with per-repo results. POST /api/actions/{slug}/run → trigger (409 if running, 400 if repo param on global action). POST /api/actions/{slug}/toggle → enable/disable. GET /api/actions/{slug}/status → running state.

## Requirements

#### ADDED: Action REST API
GET /api/actions → list definitions with target counts. GET /api/actions/{slug}/runs → run history. GET /api/actions/{slug}/runs/{id} → run detail with per-repo results. POST /api/actions/{slug}/run → trigger (409 if running, 400 if repo param on global action). POST /api/actions/{slug}/toggle → enable/disable. GET /api/actions/{slug}/status → running state.

## Acceptance Criteria

```gherkin
Feature: Action REST API
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Action REST API is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Action REST API
   → verify: `curl -s http://localhost:8000/api/actions | python -c 'import json,sys; d=json.load(sys.stdin); assert isinstance(d, list)'`

## Verification

Run runnable verify commands:
```bash
curl -s http://localhost:8000/api/actions | python -c 'import json,sys; d=json.load(sys.stdin); assert isinstance(d, list)'
```
