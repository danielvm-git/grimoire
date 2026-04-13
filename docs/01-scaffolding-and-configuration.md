# Module 1: Project Scaffolding & Configuration

Set up the project skeleton, dependencies, configuration schema, database models, and dev tooling. Everything subsequent builds on this.

**Dependencies:** None.

## 1.1 — pyproject.toml

Update `pyproject.toml` with project metadata and all dependencies:

```toml
[project]
name = "grimoire"
description = "Self-hostable GitHub repository monitoring dashboard"
```

**Runtime dependencies:**

- `fastapi` — web framework
- `uvicorn[standard]` — ASGI server
- `jinja2` — templating
- `httpx` — async HTTP client for GitHub API
- `pyyaml` — YAML config parsing
- `pydantic` — config validation
- `sqlmodel` — ORM (SQLAlchemy + Pydantic)
- `aiosqlite` — async SQLite driver
- `apscheduler` (v3) — task scheduling
- `prometheus-client` — metrics
- `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi` — structured logging
- `python-multipart` — form handling

**Dev dependencies** (extend existing):

- Keep existing: `ruff`, `pyright`, `codespell`, `vulture`, `pytest`, `pytest-cov`, `pytest-sugar`
- Add: `pytest-asyncio`, `respx` (httpx mocking), `pytest-httpx`

## 1.2 — Configuration Schema

**File:** `src/grimoire/config.py`

Parse a YAML configuration file (`config.yaml` by default, overridable via `GRIMOIRE_CONFIG` env var).

### Config file schema

```yaml
# config.yaml
# String values support env var references: "${ENV_VAR}"
github:
  token: "${GITHUB_TOKEN}"   # resolved from environment; or a literal value

git:  # entire section is optional (only needed if actions commit/push)
  user:
    name: "Luca Bello"
    email: "lusgabello@gmail.com"
  signing:                    # optional
    key_path: "/keys/id_ed25519"
    format: "ssh"             # "ssh" | "gpg"
  ssh_known_hosts: "/keys/known_hosts"  # optional

repositories:
  # Static list with optional branches
  - repo: "lucabello/grimoire"
    branches: ["main", "develop"]
  - repo: "lucabello/other-repo"
    # omitting branches → default branch only

  # From a GitHub team
  - team: "my-org/my-team"
    exclude:
      - "my-org/deprecated-repo"

staleness:
  pull_requests_days: 30   # default: 30
  issues_days: 365         # default: 365

refresh_interval_minutes: 5  # default: 5

data_dir: "./data"           # checks/ and actions/ subdirectories
workspace_dir: "./workspace" # cloned repos live here
database_path: "./grimoire.db"
log_file: "./grimoire.log"
```

### Pydantic models

- `GitHubConfig(token: str)`
- `GitUserConfig(name: str, email: str)`
- `SigningConfig(key_path: Path, format: Literal["ssh", "gpg"])`
- `GitConfig(user: GitUserConfig, signing: SigningConfig | None = None, ssh_known_hosts: Path | None = None)`
- `StaticRepoSource(repo: str, branches: list[str] = [])`
- `TeamRepoSource(team: str, exclude: list[str] = [])`
- `RepoSource` — discriminated union of the above (by field presence)
- `StalenessConfig(pull_requests_days: int = 30, issues_days: int = 365)`
- `GrimoireConfig` — top-level model; `git: GitConfig | None = None` (optional)

### Config loading

```python
def resolve_env_vars(raw: dict) -> dict:
    """
    Recursively walk the parsed YAML dict and replace any string value
    matching "${ENV_VAR}" with os.environ["ENV_VAR"].
    Raise on unset env vars (fail fast).
    """

def load_config(path: Path | None = None) -> GrimoireConfig:
    """
    1. Locate config file: explicit path → GRIMOIRE_CONFIG env var → ./config.yaml
    2. Read and parse YAML.
    3. Resolve env var references in string values.
    4. Validate with Pydantic → GrimoireConfig.
    """
```

## 1.3 — Core Domain Models

**File:** `src/grimoire/models.py`

Pydantic models for domain concepts (not DB models — those come in 1.4):

```python
class TrackedRepository(BaseModel):
    full_name: str          # "owner/repo"
    branches: list[str]     # branches to observe; empty = default branch only
    source: str             # "static" | "team:org/team-name"

class WorkflowStatus(BaseModel):
    name: str
    branch: str
    status: str             # "success" | "failure" | "pending" | "unknown"
    url: str

class RepositoryStats(BaseModel):
    full_name: str
    default_branch: str
    open_issues: int
    stale_issues: int
    open_pull_requests: int
    stale_pull_requests: int
    workflows: list[WorkflowStatus]
    warnings: list[str]     # e.g., "Failed to fetch issues", "Data is 2h stale"
    fetched_at: datetime

class CheckResult(BaseModel):
    check_name: str
    repo_full_name: str
    branch: str
    passed: bool
    output: str
    timestamp: datetime

class ActionRun(BaseModel):
    action_name: str
    triggered_by: str       # "manual" | "cron" | "api"
    started_at: datetime
    finished_at: datetime | None
    results: list[ActionRepoResult]

class ActionRepoResult(BaseModel):
    repo_full_name: str
    branch: str
    passed: bool
    output: str
```

## 1.4 — Database Setup

**File:** `src/grimoire/database.py`

SQLModel table models for persistent state:

| Table | Purpose |
|---|---|
| `CheckResultRecord` | Stores check execution results |
| `ActionRunRecord` | Stores action run metadata (name, trigger, status, timestamps) |
| `ActionRunRepoRecord` | Stores per-repo results within a run (FK to ActionRunRecord) |
| `CheckToggleRecord` | Stores check enabled/disabled state (persists across restarts) |
| `CachedRepository` | Cached repo metadata (full_name, default_branch, source, fetched_at) |
| `CachedIssue` | Cached open issues (repo, title, number, url, timestamps, fetched_at) |
| `CachedPullRequest` | Cached open PRs (repo, title, number, url, author, timestamps, fetched_at) |
| `CachedWorkflowStatus` | Cached workflow statuses (repo, name, branch, status, url, fetched_at) |
| `CachedETag` | GitHub API ETags for conditional requests (endpoint, etag, last_modified) |

**Functions to provide:**

```python
async def get_engine(database_path: str) -> AsyncEngine: ...
async def create_tables(engine: AsyncEngine) -> None: ...
async def get_session(engine: AsyncEngine) -> AsyncSession: ...
```

## 1.5 — Example Config & justfile

- Create `config.yaml.example` with the full schema documented in comments.
- Update `justfile`:
  - `dev` recipe: `uv run uvicorn grimoire.app:create_app --factory --reload --port 8000`
  - `run` recipe: `uv run uvicorn grimoire.app:create_app --factory --port 8000`
  - Keep existing `check`, `format`, `lint`, `test` recipes.
  - Add `docker-build` and `docker-run` recipes.
- Create a minimal `src/grimoire/app.py` with `create_app() -> FastAPI` that returns a FastAPI instance (routes added in later modules).

## Acceptance Criteria

- [ ] `uv sync` installs all dependencies without errors
- [ ] `just lint` passes (pyright, ruff)
- [ ] `load_config()` correctly parses the example config
- [ ] Database tables are created on startup
- [ ] `just dev` starts the server on port 8000, returns 200 on `GET /`
- [ ] Tests cover config parsing (valid input, missing fields, invalid values)
