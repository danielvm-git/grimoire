# e12s02 — MCP Tools & MCPServer

**type:** feature
**risk:** P1
**context:** e12-mcp-server
**bcps:** 1

## Context

The MCP server exposes Grimoire to AI agents. This story defines the five tools an agent can
call and the server object that registers them.

## Requirements

#### ADDED: `src/grimoire/mcp/tools.py`
`MCPToolHandlers`, bound to `(engine, checks, repos, workspace)`:

1. `list_repositories()` — `full_name`, `default_branch`, `branches`, `source`.
2. `list_checks()` — `slug`, `name`, `description`, `severity`, **`targets`**.
3. `get_repo_checks_status(repo, refresh=False)` — `overall_status` of `passing` /
   `failing` / `unknown`, counts, and per-branch `latest_results`.
4. `get_check_backlog_data(repo, refresh=False)` — delegates to `get_check_backlog`.
5. `run_repo_checks(repo, check_slug=None)` — runs checks and reports per-check
   `results_count`, `passed` and `error`.

#### ADDED: `src/grimoire/mcp/server.py`
`create_mcp_server(...)` returns an `mcp.server.MCPServer` named `"Grimoire"` with the five
tools registered.

#### Validation rules
- `validate_repo` — anchored `^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$`.
- `validate_check_slug` — anchored `^[a-zA-Z0-9_-]+$`.
- `require_tracked_repo` — rejects a repository Grimoire does not track. Format validation is
  not enough: the checks engine narrows an untracked `specific_repo` to an empty target list,
  which previously surfaced as a successful run with zero results.
- An execution that resolves no targets reports `passed=False` with an explicit error, never a
  vacuous pass (`all([])` is `True`).

## Acceptance Criteria

```gherkin
Feature: MCP tools

  Scenario: Listing repositories and checks
    Given one tracked repository and one check definition
    When the agent calls list_repositories and list_checks
    Then list_repositories returns the repository's full_name, default_branch, branches and source
    And list_checks returns the check's slug, name, description, severity and targets

  Scenario: Rejecting an untracked repository
    Given the tracked set is lucabello/grimoire
    When the agent calls run_repo_checks with acme/not-tracked
    Then a ValueError names acme/not-tracked and lists lucabello/grimoire
    And no check is executed

  Scenario: A check with no matching target is a failure
    Given a check whose targets exclude the requested repository
    When run_repo_checks runs for that repository
    Then results_count is 0
    And passed is False
    And the error says the check resolved no targets

  Scenario: Status of a repository with no results
    Given a tracked repository with no stored check results
    When get_repo_checks_status runs
    Then overall_status is "unknown"
    And latest_results is empty

  Scenario: Concurrent run conflict
    Given a check is already running
    When get_repo_checks_status is called with refresh=True
    Then the CheckConflictError is swallowed and the query still answers
```

## Steps

1. **Handlers** — implement the five handlers with validation.
   → verify: `uv run pytest tests/test_mcp/test_tools.py -v`
2. **Server** — register the tools on `MCPServer`.
   → verify: `uv run pytest tests/test_mcp/test_server.py -v`

## Verification

```bash
uv run pytest tests/test_mcp/test_tools.py -v
uv run pytest tests/test_mcp/test_tools.py --cov=grimoire.mcp.tools --cov-report=term-missing
just check
```

## Provenance

`specs/bugs/registry.yaml` — `mcp-tools-report-vacuous-success`,
`mcp-list-checks-missing-targets`, `mcp-duplicated-refresh-block`.
