# e05s01 — Action definition YAML loader

**type:** feature
**risk:** P1
**context:** e05-actions-engine
**bcps:** 2

## Context

Load YAML action definitions from {data_dir}/actions/. Derive slug from filename. ActionDefinition: name, slug, description, targets (optional — None = global), script, schedule, enabled. Duplicate slug detection.

## Requirements

#### ADDED: Action definition YAML loader
Load YAML action definitions from {data_dir}/actions/. Derive slug from filename. ActionDefinition: name, slug, description, targets (optional — None = global), script, schedule, enabled. Duplicate slug detection.

## Acceptance Criteria

```gherkin
Feature: Action definition YAML loader
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Action definition YAML loader is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Action definition YAML loader
   → verify: `python -c 'from grimoire.actions.loader import load_actions, ActionDefinition'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.actions.loader import load_actions, ActionDefinition'
```
