# e09s08 — ci-cd-migration: v3 workflow pair status check

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 1

## Context

Dedicated slim check (does NOT modify ci-cd-pipeline-audit.yaml) that
reports whether repos have migrated to the v3 CI/CD pair:
  PASS — test-build-release.yml + separate deploy.yml/deploy-*.yml
        (workflow_run trigger; deploy concurrency not cancel-in-progress)
  FAIL — primary still ci-cd-*.yml, or only embedded deploy in one file
  WARN — no recognizable workflows
Closes the visibility gap called out in issue #2 (detection rewritten for
v3; issue body’s “ci-cd-*.yml is new” logic is stale and must not be used).
Severity: warning. Targets: default branch of all tracked repos.


## Requirements

#### ADDED: ci-cd-migration: v3 workflow pair status check
Dedicated slim check (does NOT modify ci-cd-pipeline-audit.yaml) that
reports whether repos have migrated to the v3 CI/CD pair:
  PASS — test-build-release.yml + separate deploy.yml/deploy-*.yml
        (workflow_run trigger; deploy concurrency not cancel-in-progress)
  FAIL — primary still ci-cd-*.yml, or only embedded deploy in one file
  WARN — no recognizable workflows
Closes the visibility gap called out in issue #2 (detection rewritten for
v3; issue body’s “ci-cd-*.yml is new” logic is stale and must not be used).
Severity: warning. Targets: default branch of all tracked repos.


## Acceptance Criteria

```gherkin
Feature: ci-cd-migration: v3 workflow pair status check
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When ci-cd-migration: v3 workflow pair status check is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — ci-cd-migration: v3 workflow pair status check
   → verify: `test -f data/checks/ci-cd-migration.yaml`

## Verification

Run runnable verify commands:
```bash
test -f data/checks/ci-cd-migration.yaml
```
