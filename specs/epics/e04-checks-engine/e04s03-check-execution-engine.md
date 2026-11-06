# e04s03 — Check execution engine

**type:** feature
**risk:** P1
**context:** e04-checks-engine
**bcps:** 5

## Context

run_check() resets workdir, runs script via create_script_process(), captures stdout/stderr, enforces 300s timeout, caps output at 64KB. run_check_for_all_targets() resolves targets, creates CheckRunRecord, runs concurrently with Semaphore(5), marks completed. CheckProgress tracks per-check progress. is_check_running() and get_check_progress() for polling.

## Requirements

#### ADDED: Check execution engine
run_check() resets workdir, runs script via create_script_process(), captures stdout/stderr, enforces 300s timeout, caps output at 64KB. run_check_for_all_targets() resolves targets, creates CheckRunRecord, runs concurrently with Semaphore(5), marks completed. CheckProgress tracks per-check progress. is_check_running() and get_check_progress() for polling.

## Acceptance Criteria

```gherkin
Feature: Check execution engine
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Check execution engine is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Check execution engine
   → verify: `python -c 'from grimoire.checks.engine import run_check, run_check_for_all_targets'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.checks.engine import run_check, run_check_for_all_targets'
```
