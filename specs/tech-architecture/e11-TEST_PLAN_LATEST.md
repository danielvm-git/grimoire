# Test Design: e11-e2e-browser-suite

> **Epic:** e11 — End-to-End Browser Testing
> **Author:** plan-tests
> **Risk tier:** P1 (user-facing dashboard; no browser-level coverage exists today)
> **Source of truth:** Live tour of `grimoire.bigbase.click` (v0.6.0) + code read of `src/grimoire/web/**` this session.

---

## 0. Context & Gap Analysis

### What exists today
- **794-line HTTP-fragment suite** (`tests/test_web/test_router.py`, 18 classes) — asserts rendered HTML fragments via `httpx.ASGITransport`. **In-process, no DOM, no JS, no HTMX swap execution.**
- **Contract tests** (`tests/test_web/test_contract.py`) — JSON responses vs Pydantic schemas.
- **Rich reusable fixtures** (`tests/test_web/conftest.py`) — `web_client`, `web_client_with_checks`, `web_client_with_actions` seed `acme/api` + `acme/frontend` with workflows, stale issues/PRs, and check/action run history.

### What is missing (this suite closes it)
1. **No browser layer.** HTMX swaps, JS toggles, theme switch, tooltip rendering, click-through flows are never exercised in a real browser.
2. **No post-deploy verification.** `deploy.yml` ships to production the instant `test-build-release` passes — a broken template or HTMX target only surfaces when a human clicks around (as we did this session).
3. **Version drift undetected.** Live is **v0.6.0**; local `pyproject.toml` is **0.5.3**. No test asserts the deployed version.
4. **Status-icon semantics untested end-to-end.** The checkmark/X/warning/dash icons encode business rules (esp. *warning-severity check failures do not affect repo health*) that no browser test guards.

### Architecture decision — two layers
| Layer | Runner | Target | Data | Runs when |
|-------|--------|--------|------|-----------|
| **A — Hermetic E2E** | `pytest-playwright` (Python, Chromium) | locally-spawned `uvicorn` | seeded SQLite + `respx`-mocked GitHub → **deterministic exact assertions** | every PR (CI) |
| **B — Live smoke** | `pytest-playwright` (Python, Chromium) | `grimoire.bigbase.click` | production (non-deterministic) → **structural/200/render assertions only** | post-deploy in `deploy.yml` |

**Tool choice:** Playwright-for-Python (`pytest-playwright`). Rationale: reuses existing pytest infra (`asyncio_mode=auto`, `testpaths`), real Chromium, auto-waiting handles HTMX async swaps natively, one language for the whole repo. No Node/Cypress toolchain added.

**New markers:** `@pytest.mark.e2e` (Layer A, needs live server), `@pytest.mark.smoke` (Layer B, needs network). Default `just test` excludes both; `just test-e2e` / `just smoke` opt in.

---

## 1. Risk Matrix & Scenarios

Scenario ID format: `SC-e11sYY-P{tier}-NN`.
Story slices: **s01** Dashboard · **s02** Status icons & health · **s03** Repo detail · **s04** Checks · **s05** Actions · **s06** Backlog · **s07** Refresh/loading · **s08** Cross-cutting · **s09** Live smoke · **s10** NFR.

### s01 — Dashboard (matrix + list, sorting, totals)
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s01-P0-01 | `/` renders; 5 summary tiles (Repositories, Open Issues, Open PRs, Workflows, Checks) show correct seeded totals | P0 | E2E-A | `dashboard.html`, `_compute_totals` |
| SC-e11s01-P0-02 | Summary tile breakdown counts (`N failing · N warning · N healthy`) match seeded repo health mix | P0 | E2E-A | `router.py:_compute_totals` |
| SC-e11s01-P1-03 | Click each of 9 sort headers (Name, Health, Open Issues, Stale Issues, Open PRs, Stale PRs, Branches, Failing Workflows, Failing Checks, Last Activity) → HTMX swaps `dashboard-matrix`, row order changes, ▲/▼ indicator moves | P1 | E2E-A | `dashboard_matrix.html`, `SORT_KEYS` |
| SC-e11s01-P1-04 | Sort direction toggles asc↔desc on re-click of active column | P1 | E2E-A | `_build_sorted_repos` |
| SC-e11s01-P1-05 | Matrix ↔ List view toggle (`ref_17`/`ref_18`) swaps partial, preserves sort | P1 | E2E-A | `dashboard_list.html` |
| SC-e11s01-P2-06 | Stale-count coloring: `(N)` turns `text-warning` only when stale% ≥ `problematic_stale_*_pct` threshold, else `opacity-50` | P2 | E2E-A | `dashboard_matrix.html:58,63` |
| SC-e11s01-P2-07 | Repo name links to `/repo/{owner}/{name}` | P2 | E2E-A | `dashboard_matrix.html` |

### s02 — Status icons & health computation ⭐ (user-emphasized "checkmarks & icons")
Complete icon taxonomy discovered in code — **each variant gets an explicit assertion**:

| Icon | Classes | Meaning |
|------|---------|---------|
| ✓ green | `fa-check` + `status-icon-success`/`-pass` | healthy repo / workflow success / check pass |
| ✗ red | `fa-xmark` + `status-icon-failure`/`-fail` | error repo / workflow failure / error-severity check fail |
| ⚠ yellow | `fa-triangle-exclamation` + `status-icon-pending` | warning-severity check fail / staleness warning |
| — dash | `fa-minus` + `status-icon-not-run` | check never run for that repo+branch |

| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s02-P0-01 | Repo with a failing workflow renders health `fa-xmark status-icon-failure`, `title="Error…"` | P0 | E2E-A | `dashboard_matrix.html:41` |
| SC-e11s02-P0-02 | Repo with only stale items (no wf/check failures) renders health `fa-triangle-exclamation status-icon-pending`, `title="Warning…"` | P0 | E2E-A | `dashboard_matrix.html:43` |
| SC-e11s02-P0-03 | Fully green repo renders health `fa-check status-icon-success`, `title="Healthy"` | P0 | E2E-A | `dashboard_matrix.html:46` |
| SC-e11s02-P0-04 | **Business rule:** a repo whose *only* failure is a **warning-severity** check stays health=`ok`/`warning`, **NOT** `error` (warning failures excluded from health) | P0 | E2E-A | `router.py:105 health_status` |
| SC-e11s02-P1-05 | Per-branch workflow cell: `success`→green check, `failure`→red X, `pending`→pending icon | P1 | E2E-A | `dashboard_matrix.html:78` |
| SC-e11s02-P1-06 | Per-branch check cell: `pass`→check, `fail`+`severity=warning`→triangle, `fail`→X, else→`fa-minus` (not-run) | P1 | E2E-A | `dashboard_matrix.html:98-101` |
| SC-e11s02-P1-07 | Check cell links to `/checks?expand={slug}&result={id}#check-card-{slug}` deep-link | P1 | E2E-A | `dashboard_matrix.html:97` |
| SC-e11s02-P2-08 | Hovering a check cell reveals tooltip `data-tip="{name} ({branch}): {status}"` | P2 | E2E-A | `dashboard_matrix.html:96` |

### s03 — Repository detail page
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s03-P0-01 | `/repo/{owner}/{name}` renders header, issue/PR/branch counts, "View on GitHub" link | P0 | E2E-A | `repository.html` |
| SC-e11s03-P1-02 | Per-check "Output" button (`hx-get /partials/check-output/{id}`) expands full output panel | P1 | E2E-A | `repository.html` |
| SC-e11s03-P1-03 | Workflow run links point to `github.com/.../actions/runs/{id}` | P1 | E2E-A | `repository.html` |
| SC-e11s03-P2-04 | Unknown repo → `not_found.html` (404 page, not stacktrace) | P2 | E2E-A | `repository_detail` |

### s04 — Checks page (run · toggle · results · output · deep-link)
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s04-P0-01 | `/checks` lists all check cards | P0 | E2E-A | `checks.html` |
| SC-e11s04-P0-02 | **Run** button `POST /partials/check-run/{slug}` → button swaps to running state, status poller (`hx-get …/check-run-status/{slug}?was_running=1`) drives it back to idle on completion | P0 | E2E-A | `check_run_button.html` |
| SC-e11s04-P0-03 | **Toggle** `POST /api/checks/{slug}/toggle` flips Enable/Disable label + persists | P0 | E2E-A | `checks.html`, checks router |
| SC-e11s04-P1-04 | **Results** button loads `/partials/check-results/{slug}` with pass/fail aggregate counts (`fa-check N` / `fa-xmark N` / `fa-triangle-exclamation N`) | P1 | E2E-A | `check_results.html` |
| SC-e11s04-P1-05 | Click a result row → `/partials/check-output/{id}` shows full stdout, ≤64KB truncation banner when capped | P1 | E2E-A | `check_output.html` |
| SC-e11s04-P1-06 | Deep-link `/checks?expand={slug}&result={id}#check-card-{slug}` auto-expands the targeted card on load | P1 | E2E-A | `checks.html` JS |
| SC-e11s04-P2-07 | **Script** button reveals the check's bash source | P2 | E2E-A | `checks.html` |

### s05 — Actions page (run · toggle · history · output)
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s05-P0-01 | `/actions` lists action cards | P0 | E2E-A | `actions.html` |
| SC-e11s05-P0-02 | **Run** `POST /partials/action-run/{slug}` → running state + status poll → completion; new run appears in history | P0 | E2E-A | `action_run_button.html` |
| SC-e11s05-P0-03 | **Toggle** `POST /api/actions/{slug}/toggle` flips enabled state | P0 | E2E-A | `actions.html` |
| SC-e11s05-P1-04 | **Results** `/partials/action-results/{slug}` lists prior runs; row → `/partials/action-output/{result_id}` transcript | P1 | E2E-A | `action_results.html`, `action_output.html` |
| SC-e11s05-P2-05 | Per-repo pass/fail icons within an action run match `passed` bool | P2 | E2E-A | `action_run_detail.html` |

### s06 — Backlog (scoring · filters · export · save-weights)
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s06-P0-01 | `/backlog` renders header summary (`N items across M repos — X critical · Y other`) matching item count | P0 | E2E-A | `backlog.html` |
| SC-e11s06-P0-02 | Items sorted by score desc; each row shows score badge + repo + reason (workflow/PR/check failing) | P0 | E2E-A | `backlog_items.html`, `backlog.py` |
| SC-e11s06-P1-03 | **Save-weights** `POST /api/backlog/save-weights` persists reordered weights; reload reflects new scoring; **invalid payload → 4xx** (guard from `TestBacklogSaveWeightsValidation`) | P1 | E2E-A | `router.py save_weights` |
| SC-e11s06-P1-04 | **Export** `GET /api/backlog/export` downloads file with scores/statuses/links | P1 | E2E-A | `backlog export` |
| SC-e11s06-P1-05 | **Filters** panel narrows list via `/partials/backlog-items` without full reload | P1 | E2E-A | `backlog_items.html` |
| SC-e11s06-P2-06 | Score-tier grouping (100 workflow-fail > 80 check-fail-critical > 30 check-fail-minor) renders in correct order | P2 | E2E-A | `backlog.py` scoring |

### s07 — Refresh & loading flow
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s07-P0-01 | **Refresh** button `POST /partials/refresh-trigger` → button enters running state | P0 | E2E-A | `refresh_button.html` |
| SC-e11s07-P0-02 | Status poller `/partials/refresh-status?was_running=1` returns to idle + updates "Last updated" once GitHub fetch (mocked) resolves | P0 | E2E-A | `refresh_button.html` |
| SC-e11s07-P1-03 | Cold-start `loading.html` polls `/partials/loading-status` and auto-replaces with dashboard when ready | P1 | E2E-A | `loading.html`, `loading_progress.html` |
| SC-e11s07-P2-04 | Scheduled-refresh cron label renders (`Scheduled: */30 * * * *`) | P2 | E2E-A | `dashboard.html` |

### s08 — Cross-cutting (nav · theme · responsive · a11y basics)
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s08-P1-01 | Nav bar links (Dashboard/Backlog/Checks/Actions) route correctly + active state | P1 | E2E-A | `base.html` |
| SC-e11s08-P1-02 | **Theme toggle** (moon/sun) flips dark↔light, persists across navigation (localStorage) | P1 | E2E-A | `base.html` theme JS |
| SC-e11s08-P2-03 | Responsive: mobile viewport (375px) keeps nav usable, no horizontal body scroll | P2 | E2E-A | `base.html` |
| SC-e11s08-P2-04 | Status icons expose `title`/`aria` text so screen readers get pass/fail semantics (not color-only) | P2 | E2E-A | icon templates |
| SC-e11s08-P3-05 | Logo click returns to `/` | P3 | E2E-A | `base.html` |

### s09 — Live post-deploy smoke (Layer B, against production)
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s09-P0-01 | `/`, `/checks`, `/actions`, `/backlog` each return 200 + render their `<title>` | P0 | Smoke-B | live |
| SC-e11s09-P0-02 | One `/repo/{owner}/{name}` (first repo from dashboard) renders 200 | P0 | Smoke-B | live |
| SC-e11s09-P0-03 | **Version assertion:** footer version == expected release tag (catches the 0.6.0-vs-0.5.3 drift) | P0 | Smoke-B | live footer |
| SC-e11s09-P1-04 | Dashboard shows ≥1 status icon of each rendered class (page not blank/erroring) | P1 | Smoke-B | live |
| SC-e11s09-P1-05 | One safe read-only `hx-get` partial (e.g. dashboard-list) 200s | P1 | Smoke-B | live |
| SC-e11s09-P2-06 | No console errors on load of the 5 core pages | P2 | Smoke-B | live |

> **Smoke exclusions:** never trigger `check-run`/`action-run`/`refresh-trigger`/`save-weights` against production (mutating). Smoke is read-only.

### s10 — NFR
| Scenario ID | Behavior | Risk | Level | Target |
|-------------|----------|------|-------|--------|
| SC-e11s10-P1-01 | Dashboard first-contentful-paint < 1.5s on seeded Layer-A instance | P1 | E2E-A | perf trace |
| SC-e11s10-P2-02 | Axe-core accessibility scan on 5 core pages → 0 serious/critical violations | P2 | E2E-A | `axe-playwright-python` |
| SC-e11s10-P2-03 | Visual regression snapshots of dashboard (light+dark) + one repo page | P2 | E2E-A | Playwright screenshots |

---

## 2. Fixture Architecture & Isolation

### Layer A — Hermetic server + seeded data
- **App server:** session-scoped fixture spawns `uvicorn grimoire.app:create_app` on an ephemeral port; Playwright `base_url` points at it. Torn down after session.
- **Data factories:** promote `conftest.py:_populate_cache()` into a shared `tests/e2e/factories.py` — `make_repo()`, `make_stats()`, `make_check_result()`, `make_action_run()`, `make_backlog_item()`. Reuse the existing `acme/api` (healthy+stale mix, passing workflow) and `acme/frontend` (failing Build workflow) shapes as canonical fixtures — **the assertions in `test_router.py` already encode expected outputs; mirror them.**
- **Purpose-built health fixtures** for s02: `acme/warn-only` (single warning-severity check fail, no error fails → must stay non-error) is the linchpin for SC-e11s02-P0-04.
- **GitHub network:** `respx` intercepts all `api.github.com` calls (never hit real API — repo rule). Refresh flow (s07) mocks a fast-resolving fetch.
- **Database:** fresh `tmp_path` SQLite per test module; seed check/action run records exactly as `web_client_with_checks` / `web_client_with_actions` do.
- **Isolation:** module-level router state (`_checks`, `_actions`, `_engine`) saved/restored via the existing save-clear-restore pattern in `conftest.py` to prevent cross-test pollution.

### Layer B — Live smoke
- **No fixtures/mocks.** Reads production. Structural assertions only (200, title present, version string, icon-class presence). Zero mutations.
- **Config:** `SMOKE_BASE_URL` env (default `https://grimoire.bigbase.click`) so it can target staging too.

### Directory layout
```
tests/e2e/                    # Layer A — @pytest.mark.e2e
  conftest.py                 # live-server + browser fixtures
  factories.py                # promoted data factories
  test_dashboard.py           # s01
  test_status_icons.py        # s02  ⭐
  test_repo_detail.py         # s03
  test_checks.py              # s04
  test_actions.py             # s05
  test_backlog.py             # s06
  test_refresh.py             # s07
  test_cross_cutting.py       # s08
  test_nfr.py                 # s10
tests/smoke/                  # Layer B — @pytest.mark.smoke
  test_live_smoke.py          # s09
```

---

## 3. NFR Verification
| NFR | Requirement | Verification Command |
|-----|-------------|----------------------|
| Perf | Dashboard FCP < 1.5s (seeded) | `just test-e2e -k nfr_and_perf` (Playwright tracing) |
| A11y | 0 serious/critical axe violations on 5 pages | `axe-playwright-python` in `test_nfr.py` |
| Visual | No unintended diff vs baseline (light+dark) | `pytest --update-snapshots` to bless; CI compares |
| Determinism | Layer-A suite passes 10× with no flake | `just test-e2e --count=10` (pytest-repeat) |

---

## 4. CI / Just Integration
- **`justfile`:** add `test-e2e` (installs Chromium via `playwright install --with-deps chromium`, runs `-m e2e`), `smoke` (runs `-m smoke`). Keep `just test` / `just check` excluding both (`-m "not e2e and not smoke"`) so the pre-commit gate stays fast.
- **PR CI (`test-build-release.yml`):** add a `e2e` job after unit tests — cache Playwright browsers, run Layer A headless.
- **Deploy (`deploy.yml`):** append a **post-deploy `smoke` job** gated on the BigBase deploy step succeeding — runs Layer B against `SITE_URL`; **fail the deploy visibly if smoke fails** (closes the "ships blind" gap). This is the single highest-value addition.
- **New dev deps:** `pytest-playwright`, `pytest-base-url`, `axe-playwright-python`, `pytest-repeat` (all dev-group only; production image unaffected).

---

## 5. Out of Scope
- Load/stress testing (Locust) — separate NFR epic.
- Real GitHub API integration against live tokens — forbidden by repo rule (`respx` only).
- Cross-browser matrix (Firefox/WebKit) in v1 — Chromium-only first; expand once green.
- Auth/RBAC flows — Grimoire has no auth layer today.
- Mutating actions against production in smoke — deliberately excluded.

---

## 6. Traceability Handoff
- `plan-work` §17 Gherkin acceptance criteria **MUST** cite these `SC-e11sYY-*` IDs.
- Coverage target: **every P0 scenario is a merge-blocking E2E test**; P1 in CI non-blocking→blocking after 2 green weeks; P2/P3 best-effort.
- Suggested slice order for `slice-tasks`/`build-epic`: **s02 (icons) + s09 (smoke) first** — highest risk-reduction per line (icons encode the core business semantics; smoke stops blind deploys).
