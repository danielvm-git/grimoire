# Test Design: e12-mcp-server

> **Epic:** e12 — MCP Server & Query Layer  
> **Author:** plan-tests  
> **Risk tier:** P1 (integration surface for AI agents and external tools)  
> **Source of truth:** docs/specs/08-mcp-server.md + specs/epics/e12-mcp-server/epic.yaml  

---

## 0. Context & Gap Analysis

Grimoire exposes a Model Context Protocol (MCP) server allowing AI agents to query tracked repository health, active checks, action runs, and backlog scoring directly via standardized tool calls.

### Test Architecture — Risk-Scaled Layers

| Layer | Runner | Target | Data | Verification Command |
|---|---|---|---|---|
| **Layer A (Unit & Tool Schemas)** | `pytest` | `grimoire.mcp.tools` | In-memory SQLite + mocked services | `uv run pytest tests/test_mcp/test_tools.py` |
| **Layer B (Protocol & SSE Mount)** | `pytest` | `grimoire.mcp.server` | FastAPI TestClient + auth headers | `uv run pytest tests/test_mcp/test_server.py` |

---

## 1. Risk Matrix & Scenarios

- **P0: Authentication Enforced**: Requests without valid bearer token rejected with HTTP 401 when token is configured.
- **P0: Tool Execution Isolation**: Tool queries must be read-only and never trigger unrequested mutations.
- **P1: Response Schema Conformity**: Tool output schemas must match MCP tool call contracts.
