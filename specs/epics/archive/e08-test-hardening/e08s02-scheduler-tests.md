# e08s02 — Test scheduler registration

**type:** test
**risk:** P2
**context:** infra
**bcps:** 2

## Context

`checks/scheduler.py` (29%) and `actions/scheduler.py` (29%) have zero scheduler tests. Both are ~50-line functions that register cron jobs with APScheduler. A broken cron expression or misconfigured job ID silently breaks scheduled check/action runs with no visible error.

## Requirements

#### ADDED: Check scheduler registration tests
Verify that `register_checks()` with a mocked scheduler adds jobs for enabled checks with cron schedules, skips disabled checks, skips checks without a schedule, and uses the correct job ID format (`check:{slug}`).

#### ADDED: Action scheduler registration tests
Verify that `register_actions()` with a mocked scheduler adds jobs for enabled actions with cron schedules, skips disabled actions, and skips actions without a schedule.

## Steps

1. **Write check scheduler tests** — Mock `AsyncIOScheduler`. Call `register_checks()` with a mix of enabled/disabled checks, with/without schedules. Assert: enabled+scheduled → job added with `id=f"check:{slug}"`. Disabled → no job. No schedule → no job. → verify: `uv run pytest tests/test_checks/test_scheduler.py -v | grep -c PASSED | xargs -I{} test {} -ge 3`

2. **Write action scheduler tests** — Same pattern for `register_actions()`. Assert: enabled+scheduled → job added with `id=f"action:{slug}"`. → verify: `uv run pytest tests/test_actions/test_scheduler.py -v 2>/dev/null | grep -c PASSED | xargs -I{} test {} -ge 2 || echo "No action scheduler test file yet — create and add 2+ tests"`

3. **Verify coverage improvement** — Scheduler coverage should jump from ~29% to ≥80%. → verify: `uv run pytest tests/test_checks/test_scheduler.py --cov=src/grimoire/checks/scheduler --cov-report=term -q 2>&1 | grep 'scheduler.py' | awk '{print $4}' | sed 's/%//' | xargs -I{} test {} -ge 80`

## Out of scope

- Integration tests that run real scheduled jobs — these would need a running event loop and real workspaces
- Testing the scheduler itself (APScheduler is a third-party library)

## Risks

- **Low risk**: These are straightforward mock-based tests. The scheduler API is stable (APScheduler v3).
