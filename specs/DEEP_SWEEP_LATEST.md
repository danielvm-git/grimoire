# Deep Sweep — Hot Paths, Sequential Awaits, and Implicit State Machines

**Date:** 2026-11-03
**Scope:** `src/grimoire/**` (config, github, workspace, checks, actions, web, observability, mcp, app lifespan)

---

## Part 1 — Hot paths: unnecessary sequential `await`s

### Fixed in this sweep

| Hot path | Before | After | Why it was unnecessary |
|---|---|---|---|
| `github/service.py::load_stats_from_db` | 1 query per repo × 3 child tables = **3N sequential round-trips** | 4 queries total (bulk load + in-memory grouping) | Child rows are independent of each other; grouping is pure in-memory work |
| `github/service.py::save_stats_to_db` | 4 deletes per repo = **4N sequential round-trips** | 4 deletes total (`WHERE … IN (names)`) | Deletes for all refreshed repos target the same tables |
| `github/service.py::resolve_repositories` | one HTTP call per static/team source, **strictly serial** | bounded `asyncio.gather` (`Semaphore(10)`) | Each source resolution is network I/O and independent; determinism preserved by merging results in config order |
| `workspace/manager.py::WorkspaceManager.setup` | clone + configure + worktrees per repo, **strictly serial** (can be minutes) | bounded `asyncio.gather` (`Semaphore(10)`) **and** per-repo lock | Repos are independent; each repo is still serialized internally |
| `app.py::_do_refresh` — prune + sync | `await prune_stale_data(...)` then `await workspace.sync_all(...)` | `asyncio.gather(...)` | DB pruning and git fetching are independent |
| `app.py::_do_refresh` — default checks | `for check: await run_check_for_all_targets(...)` | `asyncio.gather` with `Semaphore(5)` | Checks are independent; each already bounds its own repo fan-out |
| `checks/scheduler.py` + `actions/scheduler.py` | job ignored `enabled` after registration | fire-time `if not X.enabled: return` | Disabling a check/action now takes effect immediately (see C1) |

### Reviewed and intentionally left sequential

| Hot path | Reason |
|---|---|
| `actions/engine.py::run_action` per `(repo, branch)` | Actions have external side effects (`gh`, PRs, commits). Serial is a deliberate safety choice; cross-repo concurrency is a candidate only with per-repo locks and idempotency review |
| `workspace/manager.py::sync_repo` branch reset loop | All worktrees share one bare object store; serial reset avoids index/ref churn |
| `github/client.py::_paginated_get` | Page N+1 depends on page N's `Link` header — inherently sequential |
| `app.py` toggle restores | Two tiny queries at startup; not worth gathering |
| `web/router.py` run-result partials | Up to 10 runs × 1 query per run; a valid future optimization, but lower value than the network paths above |

### Verification
`just check` green after the changes; new regression tests:
- `tests/test_github/test_service.py::test_resolve_merges_duplicate_sources_in_config_order`
- `tests/test_github/test_service.py::test_load_stats_groups_children_per_repo`
- `tests/test_checks/test_scheduler.py::test_scheduled_check_skips_when_disabled_at_fire_time`
- `tests/test_actions/test_scheduler.py::test_scheduled_action_skips_when_disabled_at_fire_time`

---

## Part 2 — Implicit state machines in the app

### SM1. Run lifecycle (the core "state machine as a service")

Two persisted machines with identical shape:
- `check_run.status` (`database.py::CheckRunRecord`)
- `action_run.status` (`database.py::ActionRunRecord`)

Observed states and transitions:

```text
(run requested)
      │  endpoint returns synthetic "running" (check: id=0, action: no id)
      ▼
   running ──success──▶ completed
      │
      ├──exception────▶ failed
      └──startup─────▶ interrupted   (cleanup_stale_runs, only if status='running')
```

- **Owners / dual source of truth:** in-memory `_running_checks` / `_running_actions` **and** DB `status`.
- **Non-terminal state:** `running`.
- **Terminal states:** `completed`, `failed`, `interrupted`.
- **Not modelled:** `queued`/`requested`, `cancelled`.

### SM2. Refresh lifecycle (`github/service.py`)

```text
idle ──refresh_all_stats()──▶ refreshing ──finally──▶ idle
```

- Source of truth: in-memory `_refresh_progress` (`None` = idle).
- No persistence, no lock, no owner.

### SM3. Toggle lifecycle (check/action enabled)

```text
enabled ⇄ disabled
```

- Dual source: in-memory definition flag + `check_toggle`/`action_toggle` table.
- Restored at startup only; toggling does **not** re-register scheduler jobs.

### SM4. Workspace / worktree lifecycle (`workspace/manager.py`)

```text
absent ──clone──▶ bare-present ──worktree add──▶ ready
   ▲                    │                         │
   │                    └──partial (dir, no config/fetch)  ← stuck if crash mid-clone
   └──reset/clean───────┘
worktree: absent ──add──▶ ready ; partial (dir without .git) ──cleanup──▶ recreated
```

- Transient/error state `partial worktree` is auto-repaired.
- `bare-present` with no `remote.origin.fetch`: treated as initialized forever (no repair).

### SM5. Workflow status projection (GitHub → dashboard)

```text
GitHub conclusion/status ──_map_conclusion()──▶ success | failure | pending | unknown
queued, in_progress, action_required, pending → pending
cancelled, timed_out, failure → failure
```

### SM6. ETag cache (`github/client.py`)

```text
no-cache ──200──▶ cached ; cached ──304──▶ cached (data reused) ; cached ──200──▶ cached (updated)
```

### SM7. Subprocess lifecycle (`script.py`)

```text
created ──▶ running ──EOF+wait──▶ exited(code) ; running ──timeout──▶ killed ▶ reaped
```

### SM8. App / scheduler lifecycle (`app.py`)

```text
startup ──▶ running ──▶ shutdown
empty-mode (config missing) is a terminal degraded branch.
```

---

## Part 3 — Non-terminal states (and how they can get stuck)

| State | Machine | Persistence | Terminal? | Stuck risk / exit |
|---|---|---|---|---|
| `running` | check/action run | DB + memory | **No** | No heartbeat/lease. Recovered **only** at process startup (`interrupted`). Task cancellation or worker death without restart leaves it forever |
| `refreshing` | refresh | memory only | **No** | Cleared in `finally`; invisible to other workers; check-then-act allows two concurrent refreshes |
| `enabled`/`disabled` | toggle | DB + memory | steady state | Not terminal by nature; now respected by scheduler at fire time |
| `partial worktree` | workspace | filesystem | **No** (transient) | Repaired on next `_ensure_worktree` |
| `bare-dir-present but uninitialized` | workspace | filesystem | **No** | **No repair path**; `sync_repo`/`setup` only check `exists()` |
| `pending` / `queued` / `in_progress` / `action_required` | workflow projection | DB cache | **No** | Re-evaluated only on the next refresh; no event-driven poll |
| synthetic `running` response | run API | none | **No** | Returned before the DB row exists (checks: `id=0`); may never become a real run if the background task loses the race or is dropped |

---

## Part 4 — Conflicts found

| ID | Conflict | Severity | Status |
|---|---|---|---|
| C1 | Scheduler registered jobs never re-checked `enabled`; disabling had no effect until restart | high | **Fixed** (fire-time guard) |
| C2 | Run status has two sources of truth: `action_status` reads DB, `check_status` reads memory; endpoints read memory | high | Fixed |
| C3 | API returns a synthetic `running` (and `id=0` for checks) before the run record exists — a phantom state | medium | Fixed |
| C4 | `interrupted` is terminal but invisible: history queries filter `status = 'completed'` only | medium | Fixed |
| C5 | Refresh start is check-then-act (`is_refresh_running()` then schedule) with no atomic guard → double refresh | medium | Fixed |
| C6 | `try_start_check()` marks memory-running before the background task is guaranteed to start; a dropped task leaks the flag forever | medium | Fixed |
| C7 | `setup()` did not take `_repo_lock`, racing `reset_workdir`/`sync_repo` | high | **Fixed** (per-repo lock) |
| C8 | No owner/heartbeat/lease for `running`; multi-worker unsafe, and recovery is startup-only | high | Fixed |
| C9 | Model comments under-specify states (`check_run`: "running \| completed"; `action_run` omits `interrupted`) | low | Fixed |
| C10 | Toggle state and scheduler state could diverge | high | **Fixed** (same as C1) |

---

## Part 5 — Recommended explicit model

1. **One enum, one truth.** Define `RunState(str, Enum)` (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `INTERRUPTED`, `CANCELLED`) in `database.py` and use it for both run tables.
2. **Separate "accepted" from "executing".** Add `queued` so the API can return a real persisted state instead of synthetic `running` (fixes C3).
3. **Explicit transition function.** `transition_run(session, run_id, allowed_from, to)` that asserts the current state is in `allowed_from`; it becomes the only writer of `status`.
4. **Terminal set as data.** `TERMINAL_RUN_STATES = {SUCCEEDED, FAILED, INTERRUPTED, CANCELLED}`; use it for history queries (fixes C4) and for guards.
5. **Lease/owner.** Add `owner_id`, `heartbeat_at`, `lease_expires_at`; a run is reclaimable to `interrupted` when the lease expires, not just at startup (fixes C8).
6. **One in-memory registry.** Replace the split `_running_checks` / `_running_actions` fast paths with a single "inflight" registry whose entries are created atomically with the DB transition (fixes C2/C6).
7. **Atomic refresh start.** `try_start_refresh()` mirroring `try_start_check()`, used by both the endpoint and the scheduler (fixes C5).
8. **Workspace init marker.** Treat `.bare` as ready only if a marker file (or `remote.origin.fetch` config) exists; otherwise re-run clone/fetch setup (fixes the uninitialized-bare state).
9. **Interrupted visibility.** Include `interrupted` in run history filters and render it explicitly in the UI.
