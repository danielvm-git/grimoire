# e01s04 — Domain models (Pydantic, not DB)

**type:** feature
**risk:** P1
**context:** e01-scaffolding
**bcps:** 2

## Context

TrackedRepository, WorkflowStatus, IssueDetail, PullRequestDetail, RepositoryStats, CheckResult, ActionRepoResult, ActionRun — shared domain vocabulary used across all modules.

## Requirements

#### ADDED: Domain models (Pydantic, not DB)
TrackedRepository, WorkflowStatus, IssueDetail, PullRequestDetail, RepositoryStats, CheckResult, ActionRepoResult, ActionRun — shared domain vocabulary used across all modules.

## Acceptance Criteria

```gherkin
Feature: Domain models (Pydantic, not DB)
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Domain models (Pydantic, not DB) is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Domain models (Pydantic, not DB)
   → verify: `python -c 'from grimoire.models import TrackedRepository, RepositoryStats'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.models import TrackedRepository, RepositoryStats'
```
