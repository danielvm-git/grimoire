# e06s01 — FastAPI app factory and router wiring

**type:** feature
**risk:** P1
**context:** e06-web-application
**bcps:** 4

## Context

create_app() mounts all API routers (repos, checks, actions), web router, static files, health endpoint. lifespan() orchestrates config load, DB setup, workspace setup, check/action loading, scheduler registration, background refresh. Three-tier data freshness: serve cached DB → background refresh if stale → loading page if empty.

## Requirements

#### ADDED: FastAPI app factory and router wiring
create_app() mounts all API routers (repos, checks, actions), web router, static files, health endpoint. lifespan() orchestrates config load, DB setup, workspace setup, check/action loading, scheduler registration, background refresh. Three-tier data freshness: serve cached DB → background refresh if stale → loading page if empty.

## Acceptance Criteria

```gherkin
Feature: FastAPI app factory and router wiring
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When FastAPI app factory and router wiring is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — FastAPI app factory and router wiring
   → verify: `python -c 'from grimoire.app import create_app; app=create_app(); assert app.title=="Grimoire"'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.app import create_app; app=create_app(); assert app.title=="Grimoire"'
```
