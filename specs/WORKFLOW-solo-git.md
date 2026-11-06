# WORKFLOW: solo-git — Grimoire

**Trigger:** Use for solo development on Grimoire with protected `main`, feature branches/worktrees, Conventional Commits, and semantic release.

**Integrate mode:** `release-branch` → **solo-local** (or direct fast-forward merge via `scripts/land-branch.sh`).

## Steps

| Step | Skill | Output | Verification |
|------|-------|--------|--------------|
| 1 | `survey-context` | Context bootstrap | `test -f specs/state.yaml` |
| 2 | `plan-work` / `plan-release` | Updated specs/epics and release-plan | `grep -c "verify:" specs/epics/**/-tasks.yaml` |
| 3 | `kickoff-branch` | Isolated worktree + branch | `git branch --show-current` |
| 4 | `develop-tdd` | Implementation with tests | `just test` |
| 5 | `verify-work` | UAT and verification evidence | `just check` |
| 6 | `audit-code` | Quality and convention compliance | Checklist pass |
| 7 | `commit-message` | Conventional Commit message | Conventional Commits regex |
| 8 | `release-branch` | Merge into main and push | `git log -1 --oneline` |
| 9 | `session-state` | Synced state.yaml and execution-status | `test -f specs/state.yaml` |

## Hard Gates

- Plan on `main` only — no feature development directly on `main`/`master`
- `kickoff-branch` required before any code changes
- Preflight (`just check`) MUST pass before landing
- Discovered gate failures follow the mandatory fix-or-log ladder
- No AI attribution footers in commits

## End State

- Current branch is `main`
- Clean working tree with Preflight green
