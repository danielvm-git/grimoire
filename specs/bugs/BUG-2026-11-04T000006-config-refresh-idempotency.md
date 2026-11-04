---
bug_id: BUG-2026-11-04T000006
status: fixed
severity: medium
scope: config, github, web, checks, actions
title: Config path divergence, refresh claimed state, duplicate running sources, non-idempotent toggles
---

# BUG-2026-11-04T000006: Config / refresh / status consistency

## Problem

- **Actual:**
  - `app.py:94-97` re-derives `Path("config.yaml")` instead of using
    `load_config()`’s XDG-aware path (`config.py:278-285`); save-weights can write a
    different file than the one loaded.
  - `refresh_all_stats()` sets `_refresh_active=True` before the `try`
    (`service.py:530-547`); an exception before the `try` leaves it stuck.
  - The check run-status partial reads memory only (`web/router.py:1240`); cron/MCP
    runs can be active while the UI shows idle.
  - `POST /toggle` flips the current value; a retry flips twice
    (`checks/router.py:320-337`; `actions/router.py:302-319`).
- **Expected:** one config path; refresh always resets; status reads DB as truth;
  toggles accept a desired state.

## TDD Fix Plan

1. **RED:**
   - `tests/test_config.py::test_resolve_config_path_matches_load_config`.
   - `tests/test_github/test_service.py::test_refresh_exception_resets_active`.
   - `tests/test_web/test_router.py::test_check_status_partial_falls_back_to_db`.
   - `tests/test_checks/test_router.py::test_put_enabled_is_idempotent`.
2. **GREEN:**
   - Extract `resolve_config_path()` in `config.py`; use it in `load_config` and `app.py`.
   - Set `_refresh_progress` and `_refresh_active` synchronously, then enter `try`.
   - Add the DB fallback to `check_run_status_partial`.
   - Add `PUT /checks/{slug}/enabled` and `PUT /actions/{slug}/enabled`; keep POST
     as a deprecated alias.
3. **verify:** `uv run pytest tests/test_config.py tests/test_github/test_service.py tests/test_web/test_router.py tests/test_checks/test_router.py -q`

## Acceptance Criteria

- [ ] Save-weights writes the loaded config path.
- [ ] A refresh exception resets `is_refresh_running()`.
- [ ] The check partial falls back to the DB.
- [ ] Replaying a PUT enabled request is idempotent.
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
