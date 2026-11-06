# e01s01 — pyproject.toml with all runtime and dev dependencies

**type:** feature
**risk:** P1
**context:** e01-scaffolding
**bcps:** 2

## Context

Set up project metadata, dependency declarations (fastapi, uvicorn, jinja2, httpx, pyyaml, pydantic, sqlmodel, aiosqlite, apscheduler, prometheus-client, opentelemetry), dev dependencies (ruff, pyright, codespell, vulture, pytest, pytest-asyncio, respx), and hatchling build backend.

## Requirements

#### ADDED: pyproject.toml with all runtime and dev dependencies
Set up project metadata, dependency declarations (fastapi, uvicorn, jinja2, httpx, pyyaml, pydantic, sqlmodel, aiosqlite, apscheduler, prometheus-client, opentelemetry), dev dependencies (ruff, pyright, codespell, vulture, pytest, pytest-asyncio, respx), and hatchling build backend.

## Acceptance Criteria

```gherkin
Feature: pyproject.toml with all runtime and dev dependencies
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When pyproject.toml with all runtime and dev dependencies is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — pyproject.toml with all runtime and dev dependencies
   → verify: `uv sync --frozen && echo OK`

## Verification

Run runnable verify commands:
```bash
uv sync --frozen && echo OK
```
