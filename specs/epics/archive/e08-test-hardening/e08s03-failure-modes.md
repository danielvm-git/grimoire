# e08s03 — Failure-mode tests for engine edge cases

**type:** test
**risk:** P1
**context:** infra
**bcps:** 4

## Context

Check and action engines handle the happy path well (timeout, exit codes, output capture). But real-world failures — disk full during workspace setup, SQLite corruption, GitHub returning malformed JSON, concurrent race conditions — have no test coverage. These are the failures that cause silent data loss or stuck processes.

## Requirements

#### ADDED: Disk-full simulation test
Simulate a read-only workspace directory and verify the engine catches the OSError gracefully, records a failure result, and does not crash.

#### ADDED: SQLite corruption test
Create a truncated/corrupt SQLite file and verify database operations surface errors as warnings, not crashes.

#### ADDED: Malformed API response test
Mock GitHub client returning invalid JSON and verify the service layer produces a warning, not an unhandled exception.

#### ADDED: Concurrent action run race test
Trigger the same action twice simultaneously and verify the concurrent-run guard correctly rejects the second invocation with a 409.

## Steps

1. **Disk-full test for check engine** — Patch `workspace.reset_workdir()` to raise `OSError(28, "No space left on device")`. Verify `run_check()` returns a failed `CheckResult` with the error in output. → verify: `uv run pytest tests/test_checks/test_engine.py -v -k "disk_full" | grep -c PASSED | xargs -I{} test {} -ge 1`

2. **SQLite corruption test** — Write a truncated SQLite file to `tmp_path`, attempt to run `run_check()` with it as the engine DB. Verify the error is caught and a failed result is persisted. → verify: `uv run pytest tests/test_checks/test_engine.py -v -k "corrupt" | grep -c PASSED | xargs -I{} test {} -ge 1`

3. **Malformed JSON test for GitHub service** — Mock `GitHubClient.get_open_issues()` to return a string instead of list/dict. Verify `fetch_repository_stats()` catches the error and populates `warnings`. → verify: `uv run pytest tests/test_github/test_service.py -v -k "malformed" | grep -c PASSED | xargs -I{} test {} -ge 1`

4. **Concurrent action run race test** — Create two `asyncio.Task`s that both call `run_action()` for the same slug. Verify the first succeeds, the second raises `ActionConflictError`. → verify: `uv run pytest tests/test_actions/test_engine.py -v -k "race" | grep -c PASSED | xargs -I{} test {} -ge 1`

5. **Action engine workspace failure test** — Patch `workspace.sync_repo()` to raise `WorkspaceError`. Verify `run_action()` catches it, records a failed result, and continues to the next repo. → verify: `uv run pytest tests/test_actions/test_engine.py -v -k "workspace_failure" | grep -c PASSED | xargs -I{} test {} -ge 1`

## Out of scope

- Fuzz testing or property-based testing
- Network partition simulation
- Real filesystem corruption tests (too destructive for unit tests)

## Risks

- **Hard to simulate**: Some failure modes (disk full) require careful monkeypatching. Mitigation: use `unittest.mock.patch` with `side_effect`, which is well-tested in Python.
- **Fragile tests**: Tests that depend on internal exception handling may break on refactors. Mitigation: assert on observable outcomes (result.passed, result.output), not on internal state.
