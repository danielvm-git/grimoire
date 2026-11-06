# e04s01 — Check definition YAML loader

**type:** feature
**risk:** P1
**context:** e04-checks-engine
**bcps:** 3

## Context

Load YAML check definitions from {data_dir}/checks/. Derive slug from filename. Validate via Pydantic: CheckDefinition (name, slug, description, targets, script, schedule, enabled, severity). TargetSpec with exactly-one validation. Duplicate slug detection.

## Requirements

#### ADDED: Check definition YAML loader
Load YAML check definitions from {data_dir}/checks/. Derive slug from filename. Validate via Pydantic: CheckDefinition (name, slug, description, targets, script, schedule, enabled, severity). TargetSpec with exactly-one validation. Duplicate slug detection.

## Acceptance Criteria

```gherkin
Feature: Check definition YAML loader
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Check definition YAML loader is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Check definition YAML loader
   → verify: `python -c 'from grimoire.checks.loader import load_checks, CheckDefinition'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.checks.loader import load_checks, CheckDefinition'
```
