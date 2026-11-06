# E12 Security Threat Model — MCP Server & Query Layer

**Epic:** e12 (Model Context Protocol Server & Check Query Service)  
**Scope:** FastMCP server, SSE transport endpoint mounting, token auth middleware, tool handlers  
**Risk Level:** Medium (network exposure over SSE, executing repository checks on demand)

---

## Threat Analysis

### 1. Unauthorized SSE Endpoint Access
**Threat:** Malicious actors on the local network or through SSRF access the `/mcp` SSE endpoint to query repository secrets, logs, or triggers.  
**Mitigation:**
- `MCPAuthMiddleware` requires an exact match on `X-MCP-Token` or `Authorization: Bearer <token>` when `mcp.token` is configured.
- Absence of configured token logs a mandatory warning on startup (F20).
- Acceptance: *LOW* when token is set; operator warned when disabled.

### 2. Command & Parameter Injection via Tool Inputs
**Threat:** Attacker passes crafted repository names or check slugs (e.g. `foo; rm -rf /`) to `run_repo_checks` or `get_repo_checks_status`.  
**Mitigation:**
- Strict regex validation in `validate_repo` (`^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$`) and `validate_check_slug` (`^[a-zA-Z0-9_-]+$`).
- Shell invocation in check engine uses parameter arrays or single-argument sanitization.
- Acceptance: *LOW* — rejected with ValueError prior to database or process invocation.

### 3. Denial of Service via Concurrent Execution Flooding
**Threat:** Rapid calls to `run_repo_checks` exhaust system process slots or SQLite connections.  
**Mitigation:**
- `run_check_for_all_targets` catches `CheckConflictError` and rejects concurrent runs gracefully.
- Concurrency bounded via semaphores.
- Acceptance: *LOW*.

### 4. Information Disclosure in Check Logs
**Threat:** Large check failure logs contain sensitive configuration or environment variables.  
**Mitigation:**
- Subprocess output capped at 64 KB; sensitive variables masked.
- Acceptance: *LOW*.

## Risk Summary

| Threat | CVSS | Mitigation | Verdict |
|---|---|---|---|
| Unauthenticated SSE Access | 4.5 | Token header / Bearer auth middleware | Acceptable |
| Input Parameter Injection | 5.0 | Regex format validation for repo & slug | Acceptable |
| Concurrent Run DoS | 3.5 | CheckConflictError handling + concurrency bounding | Acceptable |
| Log Secret Exposure | 3.0 | 64 KB truncation + env scrubbing | Acceptable |

**Overall Epic Risk: LOW** ✓
