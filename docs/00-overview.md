# Grimoire — Project Overview

Grimoire is a self-hostable web application for monitoring GitHub repositories. It aggregates repository health data (issues, PRs, CI status), runs user-defined checks and actions against repos, and presents everything in a compact, sortable dashboard.

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.13+ | Automation-native, rapid iteration, existing project setup |
| Web framework | FastAPI | Async, auto OpenAPI docs, Pydantic integration |
| Frontend | Jinja2 + HTMX + Tailwind/DaisyUI | Single deployment unit, no JS build step |
| Database | SQLite via aiosqlite + SQLModel | Zero-config, self-hosting friendly, persistent cache |
| Scheduling | APScheduler (v3) | In-process cron, stable, SQLite job store |
| GitHub API | httpx (async) | Lightweight, async-native HTTP client |
| Observability | prometheus-client + opentelemetry-sdk | Standard tooling |
| Deployment | Docker | Bundles system deps (git, gh, gpg, ssh) |
| Command runner | just | Already in project |

## Project Structure

```
grimoire/
├── src/grimoire/
│   ├── __init__.py
│   ├── app.py                    # FastAPI application factory
│   ├── config.py                 # YAML config schema + loading
│   ├── models.py                 # Core domain models (shared)
│   ├── database.py               # SQLModel engine + session
│   ├── targeting.py              # Shared target resolution (list/regex/script)
│   ├── github/
│   │   ├── __init__.py
│   │   ├── client.py             # Low-level GitHub API wrapper
│   │   ├── service.py            # High-level: resolve repos, fetch stats
│   │   └── router.py             # REST API: repos list, detail, refresh
│   ├── workspace/
│   │   ├── __init__.py
│   │   └── manager.py            # Clone, pull, branch checkout, git identity
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── loader.py             # Load YAML check definitions
│   │   ├── engine.py             # Execute checks, capture output
│   │   ├── scheduler.py          # Schedule check runs
│   │   └── router.py             # REST API: trigger, toggle, list
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── loader.py             # Load YAML action definitions
│   │   ├── engine.py             # Execute actions, capture output
│   │   ├── scheduler.py          # Schedule action runs
│   │   └── router.py             # REST API: trigger, list, get run details
│   ├── history/
│   │   ├── __init__.py
│   │   └── router.py             # REST API: time-series history data
│   ├── web/
│   │   ├── __init__.py
│   │   ├── router.py             # HTML page routes
│   │   ├── templates/            # Jinja2 templates
│   │   │   ├── base.html
│   │   │   ├── dashboard.html
│   │   │   ├── repository.html
│   │   │   └── actions.html
│   │   └── static/
│   │       └── styles.css        # Tailwind output
│   └── observability/
│       ├── __init__.py
│       ├── metrics.py            # Prometheus metrics definitions
│       └── logging.py            # OTel structured logging setup
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_github/
│   ├── test_workspace/
│   ├── test_checks/
│   ├── test_actions/
│   ├── test_history/
│   └── test_web/
├── data/                          # User-populated, mounted in Docker
│   ├── checks/                    # Check definition YAML files
│   └── actions/                   # Action definition YAML files
├── pyproject.toml
├── justfile
├── Dockerfile
├── config.yaml.example
└── README.md
```

## Module Dependency Graph

Modules are ordered by dependency. Each module may depend on previous ones but never on later ones.

```
Module 1: Scaffolding & Configuration  ──(no deps)
    │
    ├──► Module 2: GitHub Data Service
    │        │
    ├──► Module 3: Workspace Manager
    │        │
    ├──► Module 4: Checks Engine  ◄── Module 3
    │        │
    ├──► Module 5: Actions Engine  ◄── Module 3, Module 4 (shared targeting)
    │
    ├──► Module 6: Web Application  ◄── Modules 2, 4, 5
    │        │
    │        └──► Module 7: Observability & DevOps
    │
    └──► Module 8: History  ◄── Modules 1, 2, 6
```

## Configuration File (`config.yaml`)

```yaml
# GitHub authentication
# Supports environment variable references: "${ENV_VAR}"
github:
  token: "${GITHUB_TOKEN}"   # or a literal: "ghp_your_token_here"

# Git user for commits/PRs made by actions
git:
  user:
    name: "Your Name"
    email: "you@example.com"
  signing:
    key_path: "/keys/id_ed25519"
    format: "ssh"  # "ssh" or "gpg"
  ssh_known_hosts: "/keys/known_hosts"

# Repositories to track
repositories:
  # Individual repo with specific branches
  - repo: "owner/repo-name"
    branches: ["main", "develop"]

  # Individual repo (default branch only)
  - repo: "owner/another-repo"

  # Workflow filtering (include/exclude with glob patterns)
  - repo: "owner/filtered-repo"
    workflows:
      include: ["CI", "Tests *"]   # only track these workflows
      exclude: ["Publish *"]       # exclude these (applied after include)

  # All repos from a GitHub team (archived repos are always excluded)
  - team: "org-name/team-slug"
    exclude:
      - "org-name/excluded-repo"
    workflows:
      exclude: ["Release *"]       # applies to all repos from this team

# Staleness thresholds
staleness:
  pull_requests_days: 30   # PRs with no push/comment for this many days
  issues_days: 365         # Issues with no comment for this many days

# History snapshot retention
history:
  retention_days: 90       # Keep daily snapshots for this many days (default: 90)

# Data refresh interval (also default check/action frequency)
refresh_interval_minutes: 5

# Paths
data_dir: "./data"           # Contains checks/ and actions/ subdirectories
workspace_dir: "./workspace" # Where repos are cloned
database_path: "./grimoire.db"
log_file: "./grimoire.log"
```

## REST API Summary

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/repos` | List all tracked repos with latest stats |
| `GET` | `/api/repos/{owner}/{name}` | Get detailed stats for one repo |
| `POST` | `/api/refresh` | Trigger an immediate data refresh |
| `GET` | `/api/checks` | List all check definitions + enabled state |
| `GET` | `/api/checks/{slug}/results` | Latest results for a check |
| `POST` | `/api/checks/{slug}/run` | Trigger check (optional `?repo=`) |
| `POST` | `/api/checks/{slug}/toggle` | Toggle check on/off |
| `GET` | `/api/actions` | List all action definitions |
| `GET` | `/api/actions/{slug}/runs` | List run history |
| `GET` | `/api/actions/{slug}/runs/{id}` | Get specific run details + logs |
| `POST` | `/api/actions/{slug}/run` | Trigger action (optional `?repo=`); 409 if running |
| `GET` | `/api/history/global` | Aggregated time-series across all repos (`?days=30`) |
| `GET` | `/api/history/{repo}` | Time-series for a single repo (`?days=30`) |
| `GET` | `/health` | Health check (for Docker HEALTHCHECK / k8s probes) |

Auto-generated OpenAPI docs are available at `/docs` (Swagger UI) and `/redoc`.

## Cross-Cutting Concerns

- **Security:** Checks and actions execute arbitrary bash scripts. This is by design (self-hosted, user-provided scripts). The application should never be exposed to untrusted users.
- **Concurrency:** GitHub API calls and check executions use bounded concurrency (`asyncio.Semaphore(10)`) to avoid overwhelming the API or the host.
- **Error handling:** Individual check/action failures never crash the application. Log errors, record failure in DB, continue with remaining repos. GitHub API failures are surfaced as per-repo warnings on the dashboard — never silent failures.
- **Disk caching:** All GitHub data is persisted to SQLite. On startup, the app loads cached data and is immediately usable. Refreshes happen in the background. The dashboard always shows the `fetched_at` timestamp so the user knows data freshness.
- **API efficiency:** Use conditional requests (ETags) and `per_page=100` to minimize GitHub API calls. GraphQL batching is deferred as a future optimization. After initial fetch, most refreshes cost zero API calls due to ETags.
- **Idempotency:** Re-running a check or action for the same repo+branch is always safe. The DB stores all results (not just latest).
- **Testing strategy:** Use `respx` for GitHub API mocking, temp directories for workspace tests, and `httpx.AsyncClient` (via FastAPI's `TestClient`) for API endpoint tests.
