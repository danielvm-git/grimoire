# BUG-01: Fix _time_ago helper AttributeError on None timestamps

## Problem
In `src/grimoire/web/router.py`, `_time_ago(dt)` raises `AttributeError: 'NoneType' object has no attribute 'tzinfo'` when `dt` is `None` (e.g. orphan check results or missing activity dates).

## Solution
Update `_time_ago` to handle `None` gracefully by returning `"never"`.

## Verification Test
Test in `tests/test_web/test_router.py` confirming `_time_ago(None) == "never"`.

## Resolution
- **Status:** fixed
- **Fix:** `if dt is None: return "never"` guard at the top of `_time_ago` in `src/grimoire/web/router.py:271`
- **Test:** `tests/test_web/test_router.py::test_time_ago_handles_none` (PASS)
- **Verified:** `just check` 514 passed, 0 warnings
