# e07s01 — Health check endpoint

**type:** feature
**risk:** P1
**context:** e07-observability
**bcps:** 1

## Context

GET /health returns JSON: status (ok/degraded), cache_age_seconds (int), version (str), tracked_repos (int). Docker HEALTHCHECK curls this endpoint. Returns 200 always (even degraded); 503 only if app is truly down.

## Requirements

#### ADDED: Health check endpoint
GET /health returns JSON: status (ok/degraded), cache_age_seconds (int), version (str), tracked_repos (int). Docker HEALTHCHECK curls this endpoint. Returns 200 always (even degraded); 503 only if app is truly down.

## Acceptance Criteria

```gherkin
Feature: Health check endpoint
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Health check endpoint is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Health check endpoint
   → verify: `curl -s http://localhost:8000/health | python -c 'import json,sys; d=json.load(sys.stdin); assert d["status"] in ("ok","degraded")'`

## Verification

Run runnable verify commands:
```bash
curl -s http://localhost:8000/health | python -c 'import json,sys; d=json.load(sys.stdin); assert d["status"] in ("ok","degraded")'
```
