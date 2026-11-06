# e07s05 — justfile with complete command set

**type:** feature
**risk:** P1
**context:** e07-observability
**bcps:** 2

## Context

Recipes: run, dev (auto-reload), check (format+lint+test), format, lint, test, coverage, build, docker-build, docker-run, docs, docs-build, clean, bump, publish, publish-docker, release, lock, scan, venv.

## Requirements

#### ADDED: justfile with complete command set
Recipes: run, dev (auto-reload), check (format+lint+test), format, lint, test, coverage, build, docker-build, docker-run, docs, docs-build, clean, bump, publish, publish-docker, release, lock, scan, venv.

## Acceptance Criteria

```gherkin
Feature: justfile with complete command set
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When justfile with complete command set is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — justfile with complete command set
   → verify: `just --list | grep -q 'check'`

## Verification

Run runnable verify commands:
```bash
just --list | grep -q 'check'
```
