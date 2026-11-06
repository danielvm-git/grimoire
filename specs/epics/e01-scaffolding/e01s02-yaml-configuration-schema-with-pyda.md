# e01s02 — YAML configuration schema with Pydantic v2 validation

**type:** feature
**risk:** P1
**context:** e01-scaffolding
**bcps:** 5

## Context

Parse config.yaml with Pydantic v2. Support ${ENV_VAR} resolution via regex. Define GitHubConfig, GitConfig, SigningConfig, WorkflowFilter, StaticRepoSource, TeamRepoSource, StalenessConfig, BacklogConfig models. Support XDG config paths via dataconfy.

## Requirements

#### ADDED: YAML configuration schema with Pydantic v2 validation
Parse config.yaml with Pydantic v2. Support ${ENV_VAR} resolution via regex. Define GitHubConfig, GitConfig, SigningConfig, WorkflowFilter, StaticRepoSource, TeamRepoSource, StalenessConfig, BacklogConfig models. Support XDG config paths via dataconfy.

## Acceptance Criteria

```gherkin
Feature: YAML configuration schema with Pydantic v2 validation
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When YAML configuration schema with Pydantic v2 validation is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — YAML configuration schema with Pydantic v2 validation
   → verify: `python -c 'from grimoire.config import load_config; c=load_config()'  (with valid config.yaml)`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.config import load_config; c=load_config()'  (with valid config.yaml)
```
