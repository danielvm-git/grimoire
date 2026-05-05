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

## Target spec {: #target-spec }

The `targets` field specifies which repositories a check runs against. Exactly **one** of the following strategies must be set:

### `list` — explicit repos

```yaml
targets:
  list:
    - "owner/repo-a"
    - "owner/repo-b"
```

### `regex` — pattern match

Matched against the full repo name (`owner/name`):

```yaml
targets:
  regex: "myorg/.*-service"
```

Use `".*"` to match all tracked repos.

### `script` — dynamic filtering

Runs the script in each repo's default branch directory. The repo is included if the script exits `0`:

```yaml
targets:
  script: |
    test -f pyproject.toml
```

Script targeting has a 30-second timeout per repo.

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
| Shell | `/bin/bash` |

### Environment variables

| Variable | Description |
|----------|-------------|
| `REPO_OWNER` | Repository owner |
| `REPO_NAME` | Repository name |
| `REPO_FULL_NAME` | `owner/name` |
| `BRANCH` | Branch being checked |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/checks` | List all check definitions and enabled state |
| `GET` | `/api/checks/{slug}/results` | Latest results for a check |
| `GET` | `/api/checks/{slug}/runs` | Run history (reverse chronological) |
| `POST` | `/api/checks/{slug}/run` | Trigger check; optional `?repo=owner/name` |
| `POST` | `/api/checks/{slug}/toggle` | Toggle enabled state |
