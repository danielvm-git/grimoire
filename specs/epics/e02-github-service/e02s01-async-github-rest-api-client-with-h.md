# e02s01 — Async GitHub REST API client with httpx

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 6

## Context

Build GitHubClient wrapping httpx.AsyncClient with Authorization header, pagination via Link rel=next, per_page=100. Typed exceptions: GitHubAPIError, RateLimitError, NotFoundError. Retry 3x with exponential backoff (1s, 2s, 4s) for transient 5xx/network errors.

## Requirements

#### ADDED: Async GitHub REST API client with httpx
Build GitHubClient wrapping httpx.AsyncClient with Authorization header, pagination via Link rel=next, per_page=100. Typed exceptions: GitHubAPIError, RateLimitError, NotFoundError. Retry 3x with exponential backoff (1s, 2s, 4s) for transient 5xx/network errors.

## Acceptance Criteria

```gherkin
Feature: Async GitHub REST API client with httpx
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Async GitHub REST API client with httpx is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Async GitHub REST API client with httpx
   → verify: `python -c 'from grimoire.github.client import GitHubClient'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.github.client import GitHubClient'
```
