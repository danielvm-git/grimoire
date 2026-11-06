# Project Context — Grimoire

## Stack

| Layer | Choice | Version |
|---|---|---|
| Language | Python 3.13+ (strict requirement) | `>=3.13` |
| Web framework | FastAPI (async, factory pattern) | `>=0.115` |
| ASGI server | Uvicorn (via CLI entrypoint) | `>=0.34` |
| Frontend | Jinja2 + HTMX + Tailwind/DaisyUI (no JS build step) | `>=3.1` |
| Database | SQLite via aiosqlite + SQLModel (ORM) | `>=0.21` / `>=0.0.22` |
| Scheduling | APScheduler v3 (AsyncIOScheduler) | `>=3.11,<4` |
| GitHub API client | httpx (async, ETag-cached, rate-limit-aware) | `>=0.28` |
| Configuration | Pydantic v2 + PyYAML + dataconfy (XDG paths) | `>=2.10` / `>=6.0` |
| Observability | prometheus-client + opentelemetry-sdk + OTel FastAPI instrumentation | `>=0.22` / `>=1.30` |
| Deployment | Docker (Python slim base + system deps: git, gpg, ssh, gh CLI) | — |
| Build | hatchling (PEP 621) | `>=1.26` |
| Package manager | uv (lock, sync, publish) | — |
| Dev tools | ruff (linter+formatter), pyright, codespell, vulture, pytest, respx | — |

## Architecture

### Pattern: Modular Monolith with Dependency Injection via Module-Level State Setters

The application is a single FastAPI deployment with these layers:

```
CLI (__main__.py) → FastAPI App Factory (app.py)
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
GitHub Service       Checks Engine       Actions Engine
  (github/)           (checks/)            (actions/)
    │                    │                    │
GitHub Client        Workspace            Workspace
  (httpx)          (bare clone +          (shared)
                    git worktrees)
    │
  SQLite DB  ←→  In-Memory Cache
```

**Key architectural decisions:**

1. **App factory pattern** (`create_app()` in `app.py`). The `uvicorn` CLI is invoked with `--factory`, and the FastAPI app is built imperatively.

2. **Startup orchestration in `lifespan`**. All initialization (config load, DB setup, workspace sync, check/action loading, scheduler registration) happens in the async lifespan context manager. This is the effective "main" of the application.

3. **Module-level state + setter functions** for dependency injection. Shared state (checks list, repos list, workspace manager, engine) is injected into routers via `set_checks_state()`, `set_actions_state()`, `set_staleness_config()`, etc. This avoids a DI framework but makes the modules aware of each other.

4. **Three-tier data freshness strategy**: On startup, cached DB data is served immediately. A background refresh is scheduled if the data is stale or absent. The dashboard shows `fetched_at` timestamps so staleness is always visible.

5. **Checks and Actions are domain-symmetric but behaviorally different**:
   - **Checks**: Run per-repo×branch, are idempotent (no side effects), have severity (`error` / `warning`), and can be `cron`-scheduled or `refresh`-driven. Concurrent (up to 5 parallel).
   - **Actions**: Run per-repo×branch (or globally if `targets: null`), are NOT idempotent (they may commit/push), are sequential per-action (don't run concurrently), and are `cron`-scheduled or manual-only.

6. **Workspace manager**: Uses bare clones + git worktrees so multiple branches share one object store. Checks/actions run in the worktree directory with per-invocation env vars (`REPO_OWNER`, `BRANCH`, etc.). Actions sync+reset before execution; checks just reset.

### Data Flow

```
Config YAML → resolve_repositories() → list[TrackedRepository]
    │
    ▼
GitHub API (httpx + ETag cache) → fetch_repository_stats()
    │
    ├──→ save_stats_to_db() → SQLite (CachedRepository, CachedIssue, ...)
    │
    └──→ In-Memory Cache (dict[str, RepositoryStats])
            │
            ├──→ REST API (/api/repos, /api/repos/{owner}/{name})
            ├──→ Web UI (Jinja2 templates, HTMX partials)
            └──→ Prometheus Metrics
```

For checks/actions, the flow is:

```
Checks Router (/api/checks/{slug}/run)
    │
    → resolve_targets() → list of (repo, branch) pairs
    → run_check_for_all_targets() → run_check() × N (concurrent, semaphore=5)
    → persist results to DB (CheckRunRecord, CheckResultRecord)
    → update Prometheus metrics
```

## Conventions (Observed)

### Project Structure

- Feature-based subpackages (`github/`, `checks/`, `actions/`, `web/`, `workspace/`, `observability/`).
- Each subpackage has `__init__.py`, often empty (no implicit re-exports).
- Domain models in `models.py` (Pydantic, not DB models).
- DB models in `database.py` (SQLModel table classes).
- API response schemas live alongside routers (in `router.py` for checks/actions, in `schemas.py` for GitHub).
- YAML loaders for checks and actions in `loader.py` within each subpackage.
- Shared utilities (`script.py`, `targeting.py`) at the top level of the package.

### Async-First

- **Everything is async.** No sync I/O in the hot path. The entire FastAPI app uses `async def` handlers.
- `asyncio.Semaphore(10)` bounds GitHub API concurrency; `asyncio.Semaphore(5)` bounds check execution concurrency.
- Background tasks use `asyncio.create_task()` or FastAPI's `BackgroundTasks`.
- The scheduler uses `AsyncIOScheduler` from APScheduler v3.

### Error Handling

- **Individual failures never crash the application.** Checks and actions catch all exceptions, log them, and record failures in the DB.
- GitHub API errors produce per-repo warnings on the dashboard (`RepositoryStats.warnings: list[str]`). Warnings are derived from `_brief_error()` — a 130-character-max, user-friendly description.
- The GitHub client raises typed exceptions (`GitHubAPIError`, `RateLimitError`, `NotFoundError`) with status codes.
- Database connections use auto-commit sessions (`AsyncSession`); no explicit transaction management beyond commit calls.
- `cleanup_stale_runs()` on startup marks any `status='running'` records as `'interrupted'` to handle crash recovery.
- Background refresh failures (on startup) are caught and logged; the app continues with whatever data is available.

### API Design

- **REST** with OpenAPI auto-documentation at `/docs` (Swagger) and `/redoc`.
- **Response schemas are Pydantic models**, declared as `response_model=` on FastAPI route decorators.
- **CamelCase** in the HTTP API (matching GitHub's conventions). Example: `checkName`, `repoFullName`.
- **snake_case** in Python domain models (internal convention).
- The web layer uses its own view-model dataclasses (`RepoViewModel`, `ActionViewModel`, `CheckViewModel`) separate from the API response schemas.
- HTMX partials return HTML fragments; they use the same template engine as full pages.

### Configuration

- **YAML** config file (`config.yaml`), validated by **Pydantic v2** with custom validators.
- **`${ENV_VAR}` interpolation**: string values that match `^\${([^}]+)}$` are resolved from the environment at load time.
- **XDG-aware** via `dataconfy`: falls back to `~/.config/grimoire/config.yaml` and `~/.local/share/grimoire/`.
- Config resolution order: explicit path → `GRIMOIRE_CONFIG` env var → `./config.yaml` → XDG path.
- **Mutable config surface**: Backlog weights can be saved back to `config.yaml` via the `POST /api/backlog/save-weights` endpoint.

### Type Safety

- **Strict `pyright`** in CI (`pyright src`). No `type: ignore` without good reason.
- **Pydantic v2** with `model_validator(mode="after")` for cross-field validation.
- **Discriminated unions** for config sources (`StaticRepoSource | TeamRepoSource`).
- **`TargetSpec`** enforces exactly-one-field via `model_validator`.
- Database models use `Optional[datetime]` for nullable columns.
- Module-level mutable state uses `global` / `noqa: PLW0603` suppression (acknowledged pattern, not an oversight).

### Observability

- **Structured JSON logging** via a custom `JsonFormatter`. Logs go to both stdout and a file. OTel trace context (`trace_id`, `span_id`) is injected when available.
- **Prometheus metrics** at `/metrics`:
  - Per-repo gauges: open issues, stale issues, open PRs, stale PRs, branches, workflow status, last commit timestamp, data fetched timestamp, oldest issue/PR age.
  - Age distribution histograms (issue and PR, with sensible buckets).
  - Performance histograms: check duration, action duration, data refresh duration.
  - GitHub API: request counter by endpoint+status, rate limit remaining/reset.
- **OTel instrumentation** for FastAPI (auto-instrumented via `opentelemetry-instrumentation-fastapi`).
- **Health check** at `/health` returns cache age and tracked repo count. Used by Docker HEALTHCHECK.

### Testing

- **`pytest` with `pytest-asyncio`** (auto mode, all tests async).
- **`respx`** for GitHub API mocking (never real API calls).
- **`httpx.AsyncClient`** (via `ASGITransport`) for API endpoint tests.
- **`tmp_path`** fixture for filesystem isolation (temp DB, temp workspace).
- **`MockWorkspace`** and factory helpers (`_check()`, `_repo()`) in test files — small, local test utilities, not shared fixtures.
- **Test mirror**: `tests/test_github/` mirrors `src/grimoire/github/`, etc. Each module gets its own test directory.
- An integration-level test (`test_app.py`) exercises the full app startup lifecycle.
- **No test coverage enforcement in CI** — `pytest-cov` is available but used manually.

### Git Workflow

- **Conventional Commits** only (`feat:`, `fix:`, `docs:`, etc.).
- **`just check`** runs `format → lint → test` as a pre-commit quality gate.
- No schema migrations — SQLModel definitions are updated directly, `grimoire.db` is deleted for schema changes during development.

## Signals / Active Considerations

### Architectural

1. **Module-level state injection is brittle.** Routers access state from other modules via module-level globals (`_checks`, `_engine`, `_repos`, etc.). The web router imports `from grimoire.checks.router import _checks` directly. This creates tight coupling between web and checks/actions that makes testing and refactoring harder. A proper DI container or context object would be more maintainable.

2. **The web router is 1527 lines.** It contains dashboard routes, HTMX partials, backlog logic, view-model building, sorting, filtering, and config save-back — all in a single file. The view-model building functions (`_build_repo_viewmodels`, `_build_checks_for_repo`, `_load_check_context`) are substantial and could be extracted.

3. **Duplicated "latest results" SQL** between `checks/router.py`, `web/router.py`, and the backlog builder. The same `MAX(timestamp)` grouped-by pattern appears in multiple places with slight variations.

4. **Checks and Actions are architecturally parallel but implemented separately.** Loaders, engines, routers, schedulers, and DB models all exist in duplicate. The differences (concurrency model, idempotency, global-action support) are real but could potentially be handled by parameterization of a shared engine.

5. **The `lifespan` function in `app.py` is the single point of truth for startup.** It's ~110 lines of orchestration with try/except blocks and error recovery. This is where all wiring happens — a change to any module's initialization often means touching `app.py`.

### Gray Areas

6. **No API versioning.** All routes are unversioned (`/api/repos`, `/api/checks`, etc.). Breaking changes would need careful handling.

7. **The GitHub client stores mutable rate-limit state on the instance** (`self._rate_limit_remaining`). This is fine for a single-worker deployment but would be lost on process restart.

8. **Script execution creates temp files on disk** for shebang scripts. The temp file cleanup is handled in `finally` blocks, but if the process is hard-killed, orphan temp files remain.

9. **Workflow status caching deliberately skips ETags** (comment in `client.py`: "ETag-based 304 responses would hide status transitions"). This is a correct design choice but means every refresh costs at least 1 API call per workflow×branch.

### Integration Points

10. **GitHub API is the sole external dependency.** No other services (no email, no notifications, no webhooks). The ETag caching strategy is well-implemented but depends entirely on GitHub's ETag behavior.

11. **`gh` CLI is installed in Docker** but only used indirectly (actions may invoke it in their scripts). The app itself doesn't call `gh`.

12. **The workspace manager uses git CLI directly** (subprocess). No GitPython or dulwich — this is a deliberate choice for reliability, at the cost of subprocess overhead.

### Debt Hotspots

13. **`test_app.py` is an integration test** that exercises the full lifespan. It can be slow and flaky, especially with file system state. Its scope and reliability should be monitored.

14. **Backlog scoring is complex** (600+ lines in `web/backlog.py`). It implements a WSJF-inspired weighted scoring with configurable category weights, workflow weights, and per-repo multipliers. Modifying the scoring algorithm requires careful testing.

15. **Output truncation is silent.** Check/action output is capped at 64KB with a warning prefix but no indication of the full output size — users can't tell if critical information was cut off.

### Conventions to Preserve

16. **All dates are UTC** (`datetime.now(timezone.utc)` via the `_utcnow()` helper in `database.py`).

17. **`from __future__ import annotations`** is used in every source file (PEP 563 deferred annotations).

18. **No `@pytest.mark.asyncio` required** — `asyncio_mode = "auto"` in `pyproject.toml`.

19. **Output is captured via PIPEd subprocess communication**, not files. This avoids disk I/O for results and makes the engine more testable.

20. **The `script.py` module is a shared utility** used by checks engine, actions engine, and targeting script evaluation — all three go through `create_script_process()`.
