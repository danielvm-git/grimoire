# e01s06 — Dev toolchain: ruff, pyright, codespell, vulture, just

**type:** feature
**risk:** P1
**context:** e01-scaffolding
**bcps:** 2

## Context

Configure ruff (line-length 99, Google pydocstyle), pyright (strict), codespell, vulture. Wire justfile with format, lint, test, check, dev, run commands.

## Requirements

#### ADDED: Dev toolchain: ruff, pyright, codespell, vulture, just
Configure ruff (line-length 99, Google pydocstyle), pyright (strict), codespell, vulture. Wire justfile with format, lint, test, check, dev, run commands.

## Acceptance Criteria

```gherkin
Feature: Dev toolchain: ruff, pyright, codespell, vulture, just
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Dev toolchain: ruff, pyright, codespell, vulture, just is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Dev toolchain: ruff, pyright, codespell, vulture, just
   → verify: `just --list | grep -q check`

## Verification

Run runnable verify commands:
```bash
just --list | grep -q check
```
