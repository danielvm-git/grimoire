---
bug_id: BUG-2026-11-04T000000
status: fixed
severity: critical
scope: database, checks, actions
title: Run lifecycle terminal states are not absorbing and startup cleanup ignores ownership
---

# BUG-2026-11-04T000000: Run lifecycle terminality and owner-scoped cleanup

## Problem

- **Actual:** `reclaim_expired_runs()` marks a run `interrupted`, then the engine's
  success/exception path overwrites it with `completed`/`failed`. `cleanup_stale_runs()`
  interrupts **every** queued/running row at startup, including a live worker's rows.
  An unknown `status` string (e.g. `cancelled`) is neither terminal nor reclaimable and
  is invisible in history.
- **Expected:** terminal states are absorbing; a live owner's lease is never stolen;
  every persisted status is a member of `RunState`; cancellation is representable.

## Root Cause Analysis

- **Code path:** `database.py:269-288` (cleanup), `346-383` (reclaim),
  `checks/engine.py:278-296`, `actions/engine.py:203-221` (unconditional writers).
- **Why it fails:** `status` is a bare `str` (`database.py:49,106`); the writers use
  `session.get()` + assignment, not a compare-and-set. `cleanup_stale_runs` has no
  owner/lease predicate. `RunState` lacks `CANCELLED` (`state.py:20-24`).
- **Risk:** Critical. A reclaimed run can be reported `completed`; a second worker
  can interrupt the first worker's runs.

## TDD Fix Plan

1. **RED:** `tests/test_database.py`
   - `test_cleanup_does_not_interrupt_live_owner` (future lease stays `running`).
   - `test_unknown_status_is_reclaimed` (status `bogus` becomes `interrupted`).
   - `tests/test_checks/test_engine.py::test_terminal_state_is_absorbing` (reclaim
     mid-run, then let the engine finish; final status must stay `interrupted`).
2. **GREEN:**
   - Add `RunState.CANCELLED` and include it in `TERMINAL_RUN_STATES`.
   - Add `transition_run(engine, model, run_id, allowed_from, to_state, *, owner_id=None)`
     using a conditional `UPDATE ... WHERE id=:id AND status IN (...)`.
   - Add `complete_run`/`fail_run` helpers and route both engines through them.
   - Make `mark_run_running` only claim a `queued` row and clear `finished_at`.
   - Make `cleanup_stale_runs` delegate to the lease-based predicates in
     `reclaim_expired_runs` (no owner-blind bulk update).
   - Reclaim rows whose status is not in `TERMINAL_RUN_STATES | RECLAIMABLE_RUN_STATES`.
   - Add `cancelled` to the history filters (`web/router.py:882,1025`).
3. **verify:** `uv run pytest tests/test_database.py tests/test_checks/test_engine.py -q`

## Acceptance Criteria

- [ ] A future lease is never interrupted by startup cleanup.
- [ ] A reclaimed run is never overwritten by the engine.
- [ ] `cancelled` is terminal and appears in history.
- [ ] An unknown status is reclaimed to `interrupted`, not stranded.
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
