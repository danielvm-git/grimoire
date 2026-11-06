# e04s07 — Severity: error vs warning

**type:** feature
**risk:** P1
**context:** e04-checks-engine
**bcps:** 2

## Context

CheckDefinition.severity field: 'error' (default, red, affects health) or 'warning' (yellow, informational only). Dashboard health tiers: error-severity failures → 'error' health, warning-severity failures → 'warning' health.

## Requirements

#### ADDED: Severity: error vs warning
CheckDefinition.severity field: 'error' (default, red, affects health) or 'warning' (yellow, informational only). Dashboard health tiers: error-severity failures → 'error' health, warning-severity failures → 'warning' health.

## Acceptance Criteria

```gherkin
Feature: Severity: error vs warning
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Severity: error vs warning is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Severity: error vs warning
   → verify: `python -c 'from grimoire.checks.loader import CheckDefinition; c=CheckDefinition(name="t",slug="t",description="d",targets={"list":["a/b"]},script="echo",severity="warning"); assert c.severity=="warning"'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.checks.loader import CheckDefinition; c=CheckDefinition(name="t",slug="t",description="d",targets={"list":["a/b"]},script="echo",severity="warning"); assert c.severity=="warning"'
```
