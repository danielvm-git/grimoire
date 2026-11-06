# e12s01 — Configuration & CheckQueryService

**type:** feature
**risk:** P1
**context:** e12-mcp-server
**bcps:** 1

## Context

The MCP server needs a configuration block so an operator can enable, disable, protect and
re-path the endpoint, and it needs a query layer that answers "what is the current status of
this repository's checks?" without duplicating the raw SQL that the web backlog already has.

## Requirements

#### ADDED: `MCPConfig` in `src/grimoire/config.py`
- `enabled: bool = True` — remove the whole MCP surface when false.
- `token: str | None = None` — optional shared secret, resolved from `${GRIMOIRE_MCP_TOKEN}`.
- `endpoint_path: str = "/mcp"` — where the SSE app is mounted.
- Wired into `GrimoireConfig` so `config.yaml` validates it.

#### ADDED: `src/grimoire/checks/queries.py`
- `get_latest_check_results(session, repo_full_name=None) -> list[CheckResultRecord]`
  returns the newest row per `(check_slug, repo_full_name, branch)` using a
  max-timestamp subquery.
- `get_check_backlog(session, repo_full_name, check_definitions=None) -> dict[str, Any]`
  classifies every definition as passing, failing or unexecuted, caps embedded output at
  64 KiB, and **keeps the branch dimension**: one entry per `(check, branch)` with a
  `branch` field on each entry.

## Acceptance Criteria

```gherkin
Feature: MCP configuration and the check query layer

  Scenario: Configuration defaults
    Given a config.yaml with no mcp block
    When GrimoireConfig is loaded
    Then mcp.enabled is True
    And mcp.endpoint_path is "/mcp"
    And mcp.token is None

  Scenario: Latest result per check and branch
    Given two lint results for acme/repo1 on branch main with different timestamps
    When get_latest_check_results runs for acme/repo1
    Then only the newer record is returned

  Scenario: A failing branch is never hidden
    Given a lint result for acme/repo1 on main that failed
    And a lint result for acme/repo1 on release that passed
    When get_check_backlog runs for acme/repo1
    Then all_passed is False
    And failing_checks contains exactly one entry whose branch is "main"

  Scenario: Unexecuted checks are reported
    Given a check definition with no stored result
    When get_check_backlog runs
    Then it appears in unexecuted_checks with status "unexecuted"
    And all_passed is False
```

## Steps

1. **Configuration** — add `MCPConfig` and wire it into `GrimoireConfig`.
   → verify: `just check`
2. **Query layer** — implement the latest-results and backlog queries.
   → verify: `uv run pytest tests/test_checks/test_queries.py -v`

## Verification

```bash
uv run pytest tests/test_checks/test_queries.py -v
just check
```

## Provenance

`specs/bugs/registry.yaml` — `check-backlog-ignores-branch` (the branch dimension was lost in
the first implementation and restored in `6e5b09c`).
