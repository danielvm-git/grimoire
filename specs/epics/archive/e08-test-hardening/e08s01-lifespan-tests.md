# e08s01 — Extract and test app.py lifespan steps

**type:** refactor
**risk:** P0
**context:** infra
**bcps:** 5

## Context

`app.py` lifespan is 110 lines of orchestration at 31% coverage — the biggest blind spot in the test suite. It handles config loading, DB setup, workspace initialization, scheduler registration, background refresh, and shutdown. A regression here breaks everything. Extract the startup sequence into testable functions with mocked dependencies.

## Requirements

#### ADDED: Testable lifespan orchestration
Extract app.py lifespan logic into discrete async functions that accept injected dependencies (config, engine, workspace, client) rather than creating them internally. This enables unit testing each orchestration step in isolation.

#### ADDED: Three-tier data freshness coverage
Backfill tests for the three cache states: fresh cache (loads synchronously), stale cache (serves immediately + background refresh), and no cache (shows loading page + background refresh).

#### ADDED: Shutdown coverage
Verify that scheduler shutdown and client close are called during app shutdown.

## Steps

1. **Extract `setup_database(config) → engine`** — Move DB engine creation and table creation into a standalone async function that accepts a config/database_path parameter and returns an engine. → verify: `uv run python -c "import asyncio; from grimoire.app import setup_database; asyncio.run(setup_database(None))"`

2. **Extract `setup_workspace(config, repos) → workspace`** — Move workspace setup into a standalone async function. Accept config and repo list, return WorkspaceManager. → verify: `uv run pytest tests/test_app.py -v -k "workspace" | grep -c PASSED`

3. **Extract three-tier freshness logic** — Extract the cache freshness check (fresh/stale/none) and background refresh decision into a pure function that returns `(repos, need_background_refresh)`. → verify: `uv run pytest tests/test_app.py -v -k "freshness\|cache\|refresh" | grep -c PASSED | xargs -I{} test {} -ge 3`

4. **Add mock-based lifespan tests** — Write tests for each extracted function using mocked GitHubClient, mocked WorkspaceManager, and mocked scheduler. Verify each orchestration step behaves correctly. → verify: `uv run pytest tests/test_app.py -v | grep -c PASSED | xargs -I{} test {} -ge 8`

5. **Add shutdown test** — Verify that when the lifespan context exits, `scheduler.shutdown()` and `client.close()` are called. → verify: `uv run pytest tests/test_app.py -v -k "shutdown" | grep -c PASSED | xargs -I{} test {} -ge 1`

6. **Verify coverage improvement** — Run coverage on app.py and confirm ≥60% (up from 31%). → verify: `uv run pytest tests/test_app.py --cov=src/grimoire/app --cov-report=term -q 2>&1 | grep 'app.py' | awk '{print $4}' | sed 's/%//' | xargs -I{} test {} -ge 60`

## Out of scope

- Refactoring the lifespan itself to use a DI container — extraction only
- Changing the behaviour of any startup step — pure refactor
- Testing the full integration path (all 30 repos, real GitHub API) — that's e2e, not unit

## Risks

- **Breaking the app startup**: Extraction must preserve the exact call order and side effects. Mitigation: run `just check` after every step, verify the app still starts.
- **Mock fidelity**: Mocked GitHubClient must behave identically to the real one for the code paths tested. Mitigation: use existing MockGitHubClient patterns from test_github/.
