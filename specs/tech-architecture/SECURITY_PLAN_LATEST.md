# Security Plan & Threat Model — Grimoire

**Document:** SECURITY_PLAN_LATEST.md  
**Scope:** Core Architecture, GitHub Integration, Subprocess Engines, and REST/MCP Endpoints  
**Methodology:** STRIDE Threat Modeling & Defense-in-Depth Analysis  

---

## 1. Assets & Trust Boundaries

### Critical Assets
1. **GitHub Personal Access Token (`GH_TOKEN` / `GITHUB_TOKEN`)**: Grants read/write access to tracked repositories and organizations.
2. **Git Object Stores & Bare Clones**: Bare repositories under `/workspace/` containing full git commit history.
3. **Execution Subprocesses**: Ephemeral bash/shebang subprocesses running in worktrees.
4. **SQLite Database (`grimoire.db`)**: Local cache of repository metadata, PR/issue states, and execution histories.

### Trust Boundaries
- **Boundary 1 (External API)**: Inbound responses from the GitHub REST API (untrusted input from repo descriptions, issue titles, commit messages).
- **Boundary 2 (Local Subprocess)**: User-configured check/action scripts executed via `asyncio.subprocess` in worktrees.
- **Boundary 3 (Network / HTTP)**: Localhost / Docker interface serving Jinja2/HTMX dashboard and MCP endpoints.

---

## 2. STRIDE Threat Analysis

| Threat Category | Specific Risk | Severity | Implemented Mitigation | Residual Risk |
|---|---|---|---|---|
| **Spoofing** | Git author identity spoofing during automated action runs | Medium | Configurable git identity (`user.name`, `user.email`) and optional GPG/SSH commit signing | Low |
| **Tampering** | Concurrent check/action runs mutating worktree files during execution | High | Per-repo asyncio locks (`_repo_lock`) and atomic clean-and-reset before execution | Low |
| **Repudiation** | Actions modifying remote branches without tracking | Medium | Detailed `ActionRunRecord` and `ActionRunRepoRecord` logged with commit SHAs and stdout/stderr | Low |
| **Information Disclosure** | Token or secret leakage in check logs or console output | High | Subprocess environment carefully isolated; secrets excluded from logs; output capped at 64KB | Low |
| **Denial of Service** | Rogue script hanging indefinitely or flooding process table | High | Strict subprocess timeouts (300s checks, 600s actions) and process-group termination (`kill_process_group`) | Low |
| **Elevation of Privilege** | Arbitrary remote code execution via untrusted HTTP payloads | Critical | Single-user local-first design; check scripts sourced strictly from local filesystem YAML files | Minimal |

---

## 3. Defensive Security Controls

### Rate Limiting & Graceful Degradation
- Client tracks `X-RateLimit-Remaining` and `X-RateLimit-Reset`.
- Automatic exponential backoff (1s, 2s, 4s) on HTTP 5xx and connection timeouts.
- Serves cached SQLite data if GitHub API is unreachable or rate-limited.

### Subprocess Isolation
- Scripts executed in new sessions (`preexec_fn=os.setsid`) to guarantee whole process group reaping on timeout or cancellation.
- Hard output buffer cap of 64KB prevents memory exhaustion from runaway stdout/stderr.

### Secret Hygiene
- Pre-commit hooks block files containing common API token patterns (`sk-`, `ghp_`, `AKIA`, private keys).
- CI workflow validates that no AI attribution or credentials are leakable in commit messages.

---

## 4. Security Verification Gates

- [x] Pre-push git guardrails (`guard-git`) prevent direct unverified pushes to `main`.
- [x] Preflight checks (`just check`) run static analysis and format gates before commit.
- [x] Security scans runnable via `just scan`.
