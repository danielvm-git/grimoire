---
bug_id: BUG-2026-11-04T000003
status: fixed
severity: high
scope: github
title: Workflow conclusion startup_failure is projected as unknown
---

# BUG-2026-11-04T000003: Workflow conclusion mapping

## Problem

- **Actual:** `_map_conclusion("startup_failure")` returns `unknown`
  (`github/service.py:476-487`). The dashboard shows gray “unknown” and the backlog
  never collects it (`web/backlog.py:255-257` only collects `failure`).
- **Expected:** `startup_failure` and `stale` are failures; every GitHub conclusion
  has an explicit mapping.

## Root Cause Analysis

- **Code path:** `github/service.py:476-487`; `models.py:30` (`status` vocabulary);
  `web/backlog.py:255-257`.
- **Why it fails:** the mapping is a partial dict with an `unknown` default; GitHub
  added `startup_failure`/`stale` conclusions after the map was written.
- **Risk:** High. A workflow that fails to start is invisible on the dashboard/backlog.

## TDD Fix Plan

1. **RED:** `tests/test_github/test_service.py::test_every_github_conclusion_maps_explicitly`
   - Assert `startup_failure -> failure`, `stale -> failure`, and every known
     conclusion is in the map.
2. **GREEN:** extend `_map_conclusion` with `startup_failure: "failure"` and
   `stale: "failure"`; keep `skipped`/`neutral` as `unknown`.
3. **verify:** `uv run pytest tests/test_github/test_service.py -q`

## Acceptance Criteria

- [ ] `startup_failure` and `stale` are `failure`.
- [ ] The mapping test covers every known GitHub conclusion.
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
