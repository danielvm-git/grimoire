# e10s02 — Docs pair renamed: test-build-release-docs + deploy-docs

**type:** feature
**risk:** P1
**context:** e10-ci-v3-migration
**bcps:** 2

## Context

App + docs cannot share the fixed v3 filenames in one repo. Commit to renamed pair:
- test-build-release-docs.yml with name: "Test Build Release Docs"
- deploy-docs.yml with workflow_run.workflows: ["Test Build Release Docs"]
Source: test-build-release-pages-mkdocs.yml + deploy-pages-mkdocs.yml
MkDocs config path remains docs/user/mkdocs.yml (not docs/mkdocs.yml).
Delete .github/workflows/ci-cd-pages-mkdocs.yml.
Remains GitHub Pages (github-pages env); no BigBase secrets.


## Requirements

#### ADDED: Docs pair renamed: test-build-release-docs + deploy-docs
App + docs cannot share the fixed v3 filenames in one repo. Commit to renamed pair:
- test-build-release-docs.yml with name: "Test Build Release Docs"
- deploy-docs.yml with workflow_run.workflows: ["Test Build Release Docs"]
Source: test-build-release-pages-mkdocs.yml + deploy-pages-mkdocs.yml
MkDocs config path remains docs/user/mkdocs.yml (not docs/mkdocs.yml).
Delete .github/workflows/ci-cd-pages-mkdocs.yml.
Remains GitHub Pages (github-pages env); no BigBase secrets.


## Acceptance Criteria

```gherkin
Feature: Docs pair renamed: test-build-release-docs + deploy-docs
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Docs pair renamed: test-build-release-docs + deploy-docs is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Docs pair renamed: test-build-release-docs + deploy-docs
   → verify: `test -f .github/workflows/test-build-release-docs.yml`

## Verification

Run runnable verify commands:
```bash
test -f .github/workflows/test-build-release-docs.yml
```
