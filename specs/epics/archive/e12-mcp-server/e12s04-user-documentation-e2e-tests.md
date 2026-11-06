# e12s04 — User Documentation & E2E Tests

**type:** feature
**risk:** P1
**context:** e12-mcp-server
**bcps:** 1

## Context

An operator has to be able to turn the MCP endpoint on, protect it, and wire a client to it
without reading the source. This story ships that documentation plus the end-to-end tests that
prove the whole path works from `create_app()` through the lifespan.

## Requirements

#### ADDED: `docs/user/reference/mcp.md`
- The `mcp:` configuration block with `enabled`, `token`, `endpoint_path`.
- The five tools with their parameters and what each returns.
- A client configuration snippet using the SSE URL and `X-MCP-Token`.
- The wire detail that list-returning tools emit **one content block per element**, not a JSON
  array.
- Nav entry in `docs/user/mkdocs.yml` under Reference.

#### ADDED: `tests/test_mcp/test_e2e.py`
- Lifespan mount with a token: unauthenticated 401, wrong token 401, valid Bearer and valid
  `X-MCP-Token` both reach the MCP app.
- `mcp.enabled: false` → `/mcp/messages/` returns 404.
- Documentation accuracy: the documented tool names and config keys exist.

#### ADDED: spec alignment
`docs/specs/08-mcp-server.md`, `docs/specs/00-overview.md` and `docs/user/reference/mcp.md`
name the real API (`MCPServer`, not `FastMCP`) and describe the shipped payloads.

## Acceptance Criteria

```gherkin
Feature: MCP documentation and end-to-end coverage

  Scenario: Lifespan mounts the MCP server with auth
    Given a config with mcp.enabled true and a token
    When create_app() runs its lifespan
    Then /mcp/messages/ returns 401 without a credential
    And /mcp/messages/ reaches the MCP app with the correct credential

  Scenario: Disabled module is absent
    Given a config with mcp.enabled false
    When create_app() runs its lifespan
    Then /mcp/messages/ returns 404

  Scenario: Documentation matches the code
    Given docs/user/reference/mcp.md
    Then it documents list_repositories, list_checks, get_repo_checks_status,
         get_check_backlog and run_repo_checks
    And it documents enabled, token and endpoint_path
    And it names no class the SDK does not export

  Scenario: Cold start smoke
    Given a real server started with GRIMOIRE_MCP_TOKEN set
    Then GET /health returns 200
    And GET /mcp/sse without a token returns 401
    And GET /mcp/sse with the token streams "event: endpoint"
```

## Steps

1. **Documentation** — write the reference page, add the nav entry, align the specs.
   → verify: `uv run pytest tests/test_mcp/test_e2e.py -v`
2. **E2E tests** — cover lifespan mounting, auth and the disabled case.
   → verify: `uv run pytest tests/test_mcp/test_e2e.py -v`
3. **Full suite** — confirm the whole preflight is green.
   → verify: `just check`

## Verification

```bash
uv run pytest tests/test_mcp/test_e2e.py -v
just check
```

## Provenance

`specs/bugs/registry.yaml` — `mcp-spec-names-stale`, `mcp-tool-tests-assert-nothing`.
