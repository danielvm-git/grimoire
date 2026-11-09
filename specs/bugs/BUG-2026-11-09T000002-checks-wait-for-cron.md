---
bug_id: BUG-2026-11-09T000002
status: fixed
severity: medium
scope: checks
title: Checks do not run at deploy time, they wait for their cron schedule
---

# BUG-2026-11-09T000002: checks wait for their schedule after a deploy

## Problem

- **Reported:** "the checks are not running at the deploy moment, they are waiting
  the schedule — they should run all the checks on the deploy moment and then go
  to schedule."
- **Actual:** `register_checks()` only wires `CronTrigger` jobs, so a
  cron-scheduled check first fires at its next window (some are `0 */6 * * *`,
  i.e. up to six hours). Schedule-less checks ran only at the end of a data
  refresh. Right after a deploy the dashboard showed almost everything as
  `not-run`.
- **Expected:** every enabled check runs once when the process starts, then the
  schedule resumes.

## Root cause

No code path triggered a check run at startup. The schedule was the only entry
point for cron checks, and `_do_refresh()` covered only the schedule-less subset
(`default_checks = [c for c in checks if c.enabled and not c.schedule]`).

## Fix

- `checks/scheduler.py: run_all_checks_once()` — runs every enabled check once
  with `triggered_by="startup"`, bounded to 5 concurrent checks, skipping checks
  that are already running (`CheckConflictError`) and logging (not raising) a
  failing check so the rest of the pass continues.
- `app.py` — called after the initial refresh and workspace setup, and from its
  own task when no background refresh is needed. The startup refresh calls
  `_do_refresh(run_schedule_less_checks=False)` so schedule-less checks are not
  executed twice on boot.
- `config.py` — new `checks.run_on_startup` (default `true`) to opt out on large
  accounts.

## Verification

Smoke run with a throwaway config (one repo, one check scheduled `0 3 * * *`, one
schedule-less check):

```
INFO Running 2 check(s) at startup before scheduling   (grimoire.checks.scheduler)
INFO Startup check pass started 2 check(s)             (grimoire.checks.scheduler)
check_run:   ('default-check','startup','completed'), ('scheduled-check','startup','completed')
check_result: 2 rows, both passed
```

Each check ran exactly once — the refresh pass did not duplicate the
schedule-less one.
