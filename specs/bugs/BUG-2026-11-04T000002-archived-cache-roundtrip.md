---
bug_id: BUG-2026-11-04T000002
status: fixed
severity: high
scope: github
title: Archived status never round-trips through the repository cache
---

# BUG-2026-11-04T000002: Archived cache round-trip

## Problem

- **Actual:** `CachedRepository.archived` is read on a 304 (`github/service.py:169-178`)
  but `save_stats_to_db()` never writes it (`service.py:648-664`). A repo that becomes
  archived is re-tracked on the next ETag 304.
- **Expected:** an archived observation is persisted; a later 304 skips the repo.

## Root Cause Analysis

- **Code path:** `github/service.py:161-200` (`_resolve_static`),
  `602-710` (`save_stats_to_db`), `879-915` (`_prune_repos_from_db`).
- **Why it fails:** the cache writer omits `archived`; the prune step deletes the row
  for a repo that is no longer active (including an archived one).
- **Risk:** High. Archived repos consume API quota and reappear on the dashboard.

## TDD Fix Plan

1. **RED:** `tests/test_github/test_service.py`
   - `test_archived_survives_304` (200 false → 200 true → 304 → still skipped).
   - `test_save_stats_persists_archived_false` (writer sets the column explicitly).
   - `test_archived_tombstone_not_pruned`.
2. **GREEN:**
   - Add `archived: bool = False` to `RepositoryStats` (or pass it through explicitly).
   - In `_resolve_static`, when the API reports `archived=True`, upsert a
     `CachedRepository(archived=True)` tombstone before returning `None`.
   - `save_stats_to_db` writes `archived=False` explicitly for tracked repos.
   - `_prune_repos_from_db` keeps rows with `archived=True`.
3. **verify:** `uv run pytest tests/test_github/test_service.py -q`

## Acceptance Criteria

- [ ] A repo observed archived is skipped on a later 304.
- [ ] The cache writer sets `archived` explicitly.
- [ ] Archived tombstones are not pruned.
- [ ] `just check` green.

## Resolution

Fixed on `fix/audit-gaps`; the TDD tests listed above pass and `just check` is green (490 passed).
