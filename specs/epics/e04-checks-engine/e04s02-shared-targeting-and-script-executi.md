# e04s02 — Shared targeting and script execution

**type:** feature
**risk:** P1
**context:** e04-checks-engine
**bcps:** 4

## Context

resolve_targets() resolves list/regex/script TargetSpec to (repo, branches) pairs. _script_matches() evaluates per-branch with 30s timeout. target_env() builds per-invocation environment. create_script_process() handles shebang scripts (temp file + chmod +x) vs /bin/sh fallback.

## Requirements

#### ADDED: Shared targeting and script execution
resolve_targets() resolves list/regex/script TargetSpec to (repo, branches) pairs. _script_matches() evaluates per-branch with 30s timeout. target_env() builds per-invocation environment. create_script_process() handles shebang scripts (temp file + chmod +x) vs /bin/sh fallback.

## Acceptance Criteria

```gherkin
Feature: Shared targeting and script execution
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Shared targeting and script execution is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Shared targeting and script execution
   → verify: `python -c 'from grimoire.targeting import resolve_targets, target_env'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.targeting import resolve_targets, target_env'
```
