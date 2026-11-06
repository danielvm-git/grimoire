# e10s01 — Python app pair: test-build-release + deploy

**type:** feature
**risk:** P1
**context:** e10-ci-v3-migration
**bcps:** 3

## Context

Adopt org workflow templates v3 for the Python app stack:
- Copy test-build-release-python.yml → .github/workflows/test-build-release.yml
- Copy deploy-python.yml → .github/workflows/deploy.yml
- Keep workflow name exactly "Test Build Release" (deploy workflow_run hard-codes it)
- APP_TYPE: python; SITE_URL: https://grimoire.bigbase.click
- Adapt toolchain: preflight via scripts/preflight.sh → `just check`
  (pyright/codespell/ruff/pytest — NOT mypy)
- Delete .github/workflows/ci-cd-python.yml
Requires GitHub Environment `production` and BIGBASE_* secrets (Track A ops).


## Requirements

#### ADDED: Python app pair: test-build-release + deploy
Adopt org workflow templates v3 for the Python app stack:
- Copy test-build-release-python.yml → .github/workflows/test-build-release.yml
- Copy deploy-python.yml → .github/workflows/deploy.yml
- Keep workflow name exactly "Test Build Release" (deploy workflow_run hard-codes it)
- APP_TYPE: python; SITE_URL: https://grimoire.bigbase.click
- Adapt toolchain: preflight via scripts/preflight.sh → `just check`
  (pyright/codespell/ruff/pytest — NOT mypy)
- Delete .github/workflows/ci-cd-python.yml
Requires GitHub Environment `production` and BIGBASE_* secrets (Track A ops).


## Acceptance Criteria

```gherkin
Feature: Python app pair: test-build-release + deploy
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Python app pair: test-build-release + deploy is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Python app pair: test-build-release + deploy
   → verify: `test -f .github/workflows/test-build-release.yml`

## Verification

Run runnable verify commands:
```bash
test -f .github/workflows/test-build-release.yml
```
