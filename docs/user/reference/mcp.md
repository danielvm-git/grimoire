# Model Context Protocol (MCP) Integration

Grimoire includes an integrated **Model Context Protocol (MCP) Server** exposing repository health, check definitions, execution results, and check failure backlogs to AI agents over Server-Sent Events (SSE).

---

## Configuration

The MCP server is configured in `config.yaml`:

```yaml
mcp:
  enabled: true                    # Enable the /mcp SSE endpoint (default: true)
  token: "${GRIMOIRE_MCP_TOKEN}"   # Optional API authentication token (default: null)
  endpoint_path: "/mcp"            # FastMCP endpoint path on FastAPI (default: "/mcp")
```

---

## Available MCP Tools

The MCP server registers 5 primary tools for AI agent interaction:

| Tool | Parameters | Description |
|---|---|---|
| `list_repositories` | None | Returns all tracked repositories and default branches. |
| `list_checks` | None | Returns loaded check definitions (slug, name, severity). |
| `get_repo_checks_status` | `repo: str`, `refresh: bool = False` | Returns overall passing/failing status and latest result summary. |
| `get_check_backlog` | `repo: str`, `refresh: bool = False` | Returns missing or failing checks with error log output snippets. |
| `run_repo_checks` | `repo: str`, `check_slug: str \| None = None` | Triggers execution of checks for a repository on demand. |

---

## Connecting AI Clients

### Antigravity / Claude Desktop / Custom Agents

To connect an AI agent to your running Grimoire instance, configure the SSE transport:

```json
{
  "mcpServers": {
    "grimoire": {
      "url": "http://localhost:8000/mcp/sse",
      "headers": {
        "X-MCP-Token": "your_grimoire_token_here"
      }
    }
  }
}
```
