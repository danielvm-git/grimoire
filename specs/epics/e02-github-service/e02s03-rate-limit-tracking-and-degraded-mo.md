# e02s03 — Rate limit tracking and degraded mode

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 3

## Context

Track X-RateLimit-Remaining and X-RateLimit-Reset from response headers. Expose remaining/reset as Prometheus metrics. is_rate_limited and is_degraded (<10%) properties. API request counter by normalized endpoint+status.

## Requirements

#### ADDED: Rate limit tracking and degraded mode
Track X-RateLimit-Remaining and X-RateLimit-Reset from response headers. Expose remaining/reset as Prometheus metrics. is_rate_limited and is_degraded (<10%) properties. API request counter by normalized endpoint+status.

## Acceptance Criteria

```gherkin
Feature: Rate limit tracking and degraded mode
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Rate limit tracking and degraded mode is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Rate limit tracking and degraded mode
   → verify: `python -c 'from grimoire.observability.metrics import API_REQUESTS, RATE_LIMIT_REMAINING'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.observability.metrics import API_REQUESTS, RATE_LIMIT_REMAINING'
```
