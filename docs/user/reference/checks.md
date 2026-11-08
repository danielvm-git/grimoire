# Checks reference

Technical reference for check definition files.

## File location

Check definitions are YAML files in the `data/checks/` directory. The filename (without `.yaml`) becomes the check's **slug** — its unique identifier.

```
data/checks/
├── has-readme.yaml       → slug: "has-readme"
├── uv-lock-fresh.yaml    → slug: "uv-lock-fresh"
└── no-fixme.yaml         → slug: "no-fixme"
```

Slug uniqueness is enforced — duplicate filenames cause a startup error.

## Definition schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Display name shown on the dashboard |
| `description` | string | Yes | — | What the check validates |
| `targets` | [TargetSpec](#target-spec) | Yes | — | Which repos to run against |
| `script` | string | Yes | — | Bash script to execute |
| `schedule` | string (cron) | No | `refresh_schedule` | Custom cron schedule |
| `enabled` | boolean | No | `true` | Whether the check runs on schedule |
| `severity` | `"error"` \| `"warning"` | No | `"error"` | How failures appear on the dashboard and in the backlog |
| `priority` | `"P0"` \| `"P1"` \| `"P2"` | No | — | Marks a [pattern check](conformance.md) and feeds the compliance score. P0 requires `severity: error`; P1 and P2 require `severity: warning` |

## Target spec {: #target-spec }

The `targets` field specifies which repositories a check runs against. Exactly **one** of the following strategies must be set:

### `list` — explicit repos

Matches whole repos; all observed branches are checked:

```yaml
targets:
  list:
    - "owner/repo-a"
    - "owner/repo-b"
```

### `regex` — pattern match

Matched against the full repo name (`owner/name`); all observed branches are checked:

```yaml
targets:
  regex: "myorg/.*-service"
```

Use `".*"` to match all tracked repos.

### `script` — dynamic (per-branch) filtering

Runs the script once for **each observed branch** of every candidate repo, in that branch's workdir. The `(repo, branch)` pair is included if the script exits `0`. This is how you scope a check to specific branches:

```yaml
targets:
  # File-existence gate — runs on every branch that has pyproject.toml
  script: |
    test -f pyproject.toml
```

```yaml
targets:
  # Default branch only
  script: '[ "$BRANCH" = "$DEFAULT_BRANCH" ]'
```

```yaml
targets:
  # Release branches only
  script: |
    case "$BRANCH" in release/*) exit 0 ;; *) exit 1 ;; esac
```

Script targeting has a 30-second timeout per branch. The target script sees the same environment variables as the check script itself (see below).

## Exit codes

| Exit code | Result |
|-----------|--------|
| `0` | Pass |
| Non-zero | Fail |

The `severity` field controls whether a failure is reported as an **error** (red, high backlog weight) or a **warning** (yellow, low backlog weight).

## Script execution environment

| Property | Value |
|----------|-------|
| Working directory | Cloned repo at the target branch |
| Timeout | 300 seconds (5 minutes) |
| Output cap | 64 KB (stdout + stderr) |
| Shell | `/bin/sh` (override with a shebang, e.g. `#!/usr/bin/env bash`) |

!!! warning "Don't use `&>` without a bash shebang"

    In the Docker image `/bin/sh` is dash, and dash reads `cmd &>/dev/null` as "run `cmd` in the background". It always succeeds, so `if ! command -v tool &>/dev/null` takes the "missing" branch every time. Write `>/dev/null 2>&1` instead.

### Environment variables

| Variable | Description |
|----------|-------------|
| `REPO_OWNER` | Repository owner |
| `REPO_NAME` | Repository name |
| `REPO_FULL_NAME` | `owner/name` |
| `BRANCH` | Branch being checked |
| `DEFAULT_BRANCH` | Default branch of the repository |
| `GH_TOKEN` / `GITHUB_TOKEN` | GitHub API token |
| `GRIMOIRE_PYTHON` | Interpreter running the server. Use it instead of bare `python3` so bundled modules such as `grimoire.conformance` are importable |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/checks` | List all check definitions and enabled state |
| `GET` | `/api/checks/{slug}/results` | Latest results for a check |
| `GET` | `/api/checks/{slug}/runs` | Run history (reverse chronological) |
| `POST` | `/api/checks/{slug}/run` | Trigger check; optional `?repo=owner/name` |
| `POST` | `/api/checks/{slug}/toggle` | Toggle enabled state |

## Bundled check: CI/CD Pipeline Audit {: #ci-cd-pipeline-audit }

`ci-cd-pipeline-audit` reads `.github/workflows/` on the default branch and prints one table row per rule. A row is `PASS`, `FAIL`, or `UNKNOWN`. `UNKNOWN` means the rule could not be verified; it never counts as a pass.

The exit code follows the worst failing severity: critical → `2`, high → `1`, otherwise `0`. The footer lists each failing rule as `[id] title — reason`, and the headline counts equal the number of non-passing rows.

| Rule | Severity | What it checks |
|------|----------|----------------|
| `7a`, `7b` | high | The default branch has required status checks (7a) and no direct push (7b). Read from the GitHub API (classic protection and rulesets). An unprotected branch fails both. If the token cannot read protection, both are `UNKNOWN` |
| `8a` | medium | Every `uses:` ref is pinned. The row names the forms found: `sha`, `digest` (`docker://…@sha256:…`), `version`, `floating-major` (`@v6`) |
| `8b` | medium | Dependency caching, read from parsed steps: `actions/cache`, `setup-python`/`setup-node` `cache:`, `setup-go` `cache: true`, `setup-uv` `enable-cache`, `rust-cache`. `cache: true` on `setup-python` is rejected by GitHub Actions and is flagged |
| `9a` | medium | Every workflow sets `permissions:` at the top level, or on every job. The row names jobs that inherit the default |
| `5e` | medium | The deploy authenticates by OIDC (`id-token: write`) or a `secrets.*` reference. The row names which |
| `3b`–`3d` | critical/high | `needs:` is followed through the whole chain, so `lint → test → verify → release → build` counts. Build-then-release and tag-then-build are both valid |
| `2a` | high | Only the primary pipeline needs a `push` trigger. Auxiliary workflows (PR bots, issue triage) are exempt |

Set `GRIMOIRE_AUDIT_STRICT_SHA_PINNING=1` in the Grimoire environment to make `8a` accept only 40-character SHAs and OCI digests. Floating tags such as `@v6` then fail.
