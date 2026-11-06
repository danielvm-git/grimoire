# e02s04 — Repository resolution from static lists and teams

**type:** feature
**risk:** P1
**context:** e02-github-service
**bcps:** 4

## Context

resolve_repositories() processes config.repositories list. StaticRepoSource: get_repo() to validate, skip archived. TeamRepoSource: get_team_repos(), exclude set, skip archived. Deduplicate by full_name; merge branch lists.

## Requirements

#### ADDED: Repository resolution from static lists and teams
resolve_repositories() processes config.repositories list. StaticRepoSource: get_repo() to validate, skip archived. TeamRepoSource: get_team_repos(), exclude set, skip archived. Deduplicate by full_name; merge branch lists.

## Acceptance Criteria

```gherkin
Feature: Repository resolution from static lists and teams
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Repository resolution from static lists and teams is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Repository resolution from static lists and teams
   → verify: `python -c 'from grimoire.github.service import resolve_repositories'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.github.service import resolve_repositories'
```
