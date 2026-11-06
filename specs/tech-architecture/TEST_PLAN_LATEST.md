# Test Architecture & Master Test Plan — Grimoire

**Document:** TEST_PLAN_LATEST.md  
**Scope:** Whole-repository test pyramid, execution gates, and test tooling  

---

## 1. Test Pyramid & Tooling

```
                     ▲
                    / \     End-to-End Browser (Playwright / Chromium)
                   /   \    pytest -m e2e / just test-e2e
                  /-----\
                 /       \   API Contract & Integration (httpx, SQLite)
                /         \  tests/test_web, tests/test_mcp, tests/test_app
               /-----------\
              /             \ Unit & Engine Tests (respx, mock workspace)
             /               \ tests/test_github, tests/test_checks, tests/test_actions
            └─────────────────┘
```

- **Unit Tests**: Fast, hermetic, respx-mocked GitHub client, isolated `tmp_path` workspaces.
- **Integration Tests**: App lifespan lifecycle (`test_app.py`), DB transaction rollbacks, concurrent task locks.
- **E2E & Smoke**: Playwright-driven browser tests exercising HTMX partial swaps and live status icons.

---

## 2. Quality Gates & Thresholds

- **Preflight Requirement**: `just check` must be green prior to any commit (format + lint + test).
- **Zero Real Network Calls**: Tests strictly intercept external calls with `respx`.
- **Async Concurrency**: Auto mode with pytest-asyncio (`asyncio_mode = "auto"`).
