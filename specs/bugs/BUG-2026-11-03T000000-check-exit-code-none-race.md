---
bug_id: BUG-2026-11-03T000000
status: fixed
severity: high
scope: checks
title: Check output reports "[exit code None]" due to unawaited subprocess reaping
---

# BUG-2026-11-03T000000: Check output reports "[exit code None]" due to unawaited subprocess reaping

## Problem

- **Actual behavior:** `just check` failed at preflight with
  `tests/test_checks/test_engine.py::TestRunCheck::test_failed_check_stderr_labeled`.
  The recorded output was `'[stderr]\noops\n\n[exit code None]'` instead of
  `'[stderr]\noops\n\n[exit code 2]'`.
- **Expected behavior:** A non-zero exit code is always reported in the output
  (`[exit code N]`), and `passed` reflects the real process status.
- **How to reproduce (order-dependent):** the test passes in isolation
  (`pytest tests/test_checks/test_engine.py::TestRunCheck::test_failed_check_stderr_labeled -q`
  → 1 passed) but fails under the full suite, where event-loop timing differs.

## Root Cause Analysis

- **Code path:** `src/grimoire/checks/engine.py::run_check` awaits
  `read_stdout_stderr_capped(proc)` and then immediately reads `proc.returncode`.
- **Why it fails:** `read_stdout_stderr_capped` (`src/grimoire/script.py`) reads
  both pipes to EOF but never awaits `proc.wait()`. Pipe EOF means the child
  closed its descriptors; it does **not** guarantee asyncio has reaped the child
  and populated `Process.returncode`. Under load the child-watcher callback runs
  later, so `returncode` is still `None` when the engine formats the output.
- **Latent second defect:** the helper drains stdout fully and only then drains
  stderr. A check that writes more than one pipe buffer (64KB) to stderr while
  stdout remains open deadlocks: the child blocks writing stderr, the parent
  blocks waiting for stdout EOF.
- **Risk level:** Low. Add `await proc.wait()` after draining, and drain both
  streams concurrently with `asyncio.gather`.

## Security impact

NONE — no exploit path. This is a reporting race in output formatting.

## TDD Fix Plan

1. **RED:** In `tests/test_script.py`, add
   `test_read_stdout_stderr_capped_awaits_process_exit` using a stub process
   whose `returncode` stays `None` until `wait()` is called, and
   `test_read_stdout_stderr_capped_reads_both_streams_concurrently` using a
   two-party `asyncio.Barrier`.
   **GREEN:** `read_stdout_stderr_capped` and `read_output_capped` drain streams
   with `asyncio.gather` and `await proc.wait()` before returning.
   **verify:** `uv run pytest tests/test_script.py -q`

2. **RED:** Re-run the order-dependent engine test under the full suite.
   **GREEN:** `just check`.
   **verify:** `just check`

**REFACTOR:** none — change is contained to the two reader helpers.

## Acceptance Criteria

- [ ] `read_stdout_stderr_capped` / `read_output_capped` return only after the
      process is reaped (`returncode` is set)
- [ ] Both streams are drained concurrently (no deadlock on large stderr)
- [ ] Order-dependent engine test passes in the full suite
- [ ] `just check` green

## Resolution

- **Fixed by:** `src/grimoire/script.py` — both `read_output_capped` and `read_stdout_stderr_capped` now drain streams concurrently via `asyncio.gather` and `await proc.wait()` before returning, guaranteeing `returncode` is populated.
- **Verification:** `uv run pytest tests/test_script.py tests/test_checks/test_engine.py -q` (all pass). Full suite `just check` 514 passed.
- **Concurrency fix:** `read_stdout_stderr_capped` uses `asyncio.gather` for stdout+stderr instead of sequential reads (avoids deadlock on large stderr).
