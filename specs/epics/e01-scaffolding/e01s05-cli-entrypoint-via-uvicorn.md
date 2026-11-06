# e01s05 — CLI entrypoint via uvicorn

**type:** feature
**risk:** P1
**context:** e01-scaffolding
**bcps:** 1

## Context

grimoire.__main__:main() runs uvicorn with app factory. Command: 'grimoire' or 'uv run uvicorn grimoire.app:create_app --factory'.

## Requirements

#### ADDED: CLI entrypoint via uvicorn
grimoire.__main__:main() runs uvicorn with app factory. Command: 'grimoire' or 'uv run uvicorn grimoire.app:create_app --factory'.

## Acceptance Criteria

```gherkin
Feature: CLI entrypoint via uvicorn
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When CLI entrypoint via uvicorn is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — CLI entrypoint via uvicorn
   → verify: `python -c 'from grimoire.__main__ import main'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.__main__ import main'
```
