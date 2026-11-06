# e09s05 — lint-passes: language-aware linter check

**type:** feature
**risk:** P1
**context:** e09-fleet-checks
**bcps:** 2

## Context

One check that auto-detects the project language and runs the appropriate
linter. Script targeting via file-existence gates: pyproject.toml → ruff,
go.mod → golangci-lint, package.json → eslint, Cargo.toml → cargo clippy,
Package.swift → swiftlint. Falls back to shellcheck for shell scripts.
Severity: warning — lint is important but shouldn't block the dashboard.


## Requirements

#### ADDED: lint-passes: language-aware linter check
One check that auto-detects the project language and runs the appropriate
linter. Script targeting via file-existence gates: pyproject.toml → ruff,
go.mod → golangci-lint, package.json → eslint, Cargo.toml → cargo clippy,
Package.swift → swiftlint. Falls back to shellcheck for shell scripts.
Severity: warning — lint is important but shouldn't block the dashboard.


## Acceptance Criteria

```gherkin
Feature: lint-passes: language-aware linter check
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When lint-passes: language-aware linter check is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — lint-passes: language-aware linter check
   → verify: `test -f data/checks/lint-passes.yaml`

## Verification

Run runnable verify commands:
```bash
test -f data/checks/lint-passes.yaml
```
