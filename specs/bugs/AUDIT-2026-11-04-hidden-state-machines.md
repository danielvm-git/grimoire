# Audit — Hidden State Machines & Testing Impact (2026-11-04)

**Source:** `specs/bugs/registry.yaml` + the 2026-11-04 hidden-state-machine audit.
**Baseline:** HEAD `912f10f`, 468 tests green, lint clean.
**Branch:** `fix/audit-gaps`.

This index links the audit findings to the fix capsules. The audit's 14 executable
checks live in `/tmp/grimoire-audit/test_audit_sketches.py` (not committed).

| Finding | Bug capsule |
|---|---|
| F1 terminal reopen, F2 owner-blind startup cleanup, F9 unknown status dead end | `BUG-2026-11-04T000000-run-lifecycle-terminality.md` |
| F3 check admission bypass, F4 memory-flag leak, F16 dead `_check_lock` | `BUG-2026-11-04T000001-check-admission-guard.md` |
| F5 archived cache round-trip | `BUG-2026-11-04T000002-archived-cache-roundtrip.md` |
| F6 `startup_failure` → unknown | `BUG-2026-11-04T000003-workflow-conclusion-mapping.md` |
| F7 partial bare clone / swallowed worktree error | `BUG-2026-11-04T000004-workspace-partial-bare.md` |
| F8 child survives cancellation | `BUG-2026-11-04T000005-subprocess-cancellation-leak.md` |
| F10 non-idempotent toggle, F11 config path divergence, F12 refresh claimed state, F13 duplicate running sources | `BUG-2026-11-04T000006-config-refresh-idempotency.md` |
| F15 dead pagination state, F18 unreachable handler, F19 metric label leak, F20 empty MCP token | `BUG-2026-11-04T000007-dead-code-observability.md` |

Design notes (not fixed): F14 (`completed` means finished, not succeeded — the
per-repo `passed` flags remain the success signal) and F17 (`not-run` is a valid
projection until the next scheduled run).
