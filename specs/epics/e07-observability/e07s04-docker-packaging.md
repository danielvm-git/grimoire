# e07s04 — Docker packaging

**type:** feature
**risk:** P1
**context:** e07-observability
**bcps:** 3

## Context

Dockerfile: python:3.13-slim base, apt install git/gpg/ssh/curl/gh, uv install, copy src + pyproject.toml + uv.lock. docker-entrypoint.sh. HEALTHCHECK via curl /health. docker-compose.yml for local dev with volume mounts.

## Requirements

#### ADDED: Docker packaging
Dockerfile: python:3.13-slim base, apt install git/gpg/ssh/curl/gh, uv install, copy src + pyproject.toml + uv.lock. docker-entrypoint.sh. HEALTHCHECK via curl /health. docker-compose.yml for local dev with volume mounts.

## Acceptance Criteria

```gherkin
Feature: Docker packaging
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Docker packaging is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Docker packaging
   → verify: `docker build -t grimoire . --quiet && echo OK`

## Verification

Run runnable verify commands:
```bash
docker build -t grimoire . --quiet && echo OK
```
