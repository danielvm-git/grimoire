# Plan Audit — Grimoire e08 (Test Hardening)
**Date:** 2026-07-09 · **Verdict:** READY (1 advisory)

## Principles Alignment

| Check | Status | Note |
|-------|--------|------|
| Vertical slices | ⚠️ | Stories are test-only layers (except e08s01 which refactors). Inherent to a Test Hardening epic — the value IS the coverage. Each story is independently shippable though. |
| Scope bounded | ✅ | All 4 stories have explicit Out of Scope sections |
| Success criteria | ✅ | 20 verify commands across 4 stories, all runnable |
| HARD GATE candidates | ✅ | e08s01: extraction must not break startup (gated by `just run` after each step). e08s04: contract tests are intentional break-on-change canaries |
| Domain language | ✅ | Consistent: "lifespan", "scheduler registration", "failure-mode", "contract test" used throughout |

## Conventions Completeness

| Check | Status | Note |
|-------|--------|------|
| CLAUDE.md / AGENTS.md | ✅ | AGENTS.md present with Reach Template, CLAUDE.md symlink |
| CONVENTIONS.md | ✅ | Present — includes Always Green, fix-or-log, Conventional Commits |
| specs/ directory | ✅ | Full bigpowers layout, 9 epics, release plan, state, execution status |
| Commit conventions | ✅ | Conventional Commits documented in AGENTS.md + CONVENTIONS.md |
| Git workflow mode | ✅ | `workflow_mode: solo-git` in state.yaml |

## Bigpowers Pre-flight

| Question | Answer |
|----------|--------|
| Test command | `just test` (uv run pytest) |
| Build command | `just build` (uv build) |
| Lint command | `just lint` (ruff + pyright + codespell + vulture) |
| Typecheck command | `uv run pyright src` (inside just lint) |
| CI platform | GitHub Actions (`.github/workflows/docs.yaml`) — no test CI yet |
| Solo or team | solo-git |
| Language + framework | Python 3.13+ / FastAPI + SQLite |
| Greenfield or existing | Existing — 391 tests, 84% coverage, 7 completed epics |

## Open Gaps

(None — advisory fixed in e08s02 task 2 verify command)

## Verdict

**READY** — 1 advisory, 0 blockers. All stories have verify commands, all are independently shippable, scope is bounded, conventions are in place. Proceed to `kickoff-branch` → `develop-tdd`.

## Recommendation

Start with e08s02 (2 BCPs, P2, easiest) as a warm-up, then e08s01 (5 BCPs, P0, highest impact) since it's the biggest coverage jump. e08s03 and e08s04 can run in parallel after.
