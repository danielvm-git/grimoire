# e01s03 — SQLite database models with SQLModel + aiosqlite

**type:** feature
**risk:** P1
**context:** e01-scaffolding
**bcps:** 4

## Context

Define CheckRunRecord, CheckResultRecord, CheckToggleRecord, ActionToggleRecord, ActionRunRecord, ActionRunRepoRecord, CachedRepository, CachedIssue, CachedPullRequest, CachedWorkflowStatus, CachedETag. Provide get_engine, create_tables, get_session helpers. Implement cleanup_stale_runs for crash recovery.

## Requirements

#### ADDED: SQLite database models with SQLModel + aiosqlite
Define CheckRunRecord, CheckResultRecord, CheckToggleRecord, ActionToggleRecord, ActionRunRecord, ActionRunRepoRecord, CachedRepository, CachedIssue, CachedPullRequest, CachedWorkflowStatus, CachedETag. Provide get_engine, create_tables, get_session helpers. Implement cleanup_stale_runs for crash recovery.

## Acceptance Criteria

```gherkin
Feature: SQLite database models with SQLModel + aiosqlite
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When SQLite database models with SQLModel + aiosqlite is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — SQLite database models with SQLModel + aiosqlite
   → verify: `python -c 'from grimoire.database import get_engine, create_tables; import asyncio; asyncio.run(get_engine(":memory:"))'`

## Verification

Run runnable verify commands:
```bash
python -c 'from grimoire.database import get_engine, create_tables; import asyncio; asyncio.run(get_engine(":memory:"))'
```
