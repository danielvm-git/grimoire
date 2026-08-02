```
STORY KEY: e11s01
TITLE:     E2E harness + status-icon semantics (tracer bullet)
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  4
SIZE:      L
```

### 1. Business narrative [draft]

Grimoire's entire test suite (`tests/test_web/test_router.py`, 794 lines) exercises HTML fragments through `httpx.ASGITransport` — an in-process HTTP client that never renders a DOM, never executes HTMX's client-side swap logic, and never runs the browser JS that drives the theme toggle or deep-link auto-expand. A live tour of production (`grimoire.bigbase.click`, v0.6.0) this session confirmed the app itself is healthy, but nothing in CI would have caught it if it weren't — the rendered-in-a-browser behavior is entirely unverified. The dashboard's status-icon system is the highest-risk piece of that unverified surface: it's the single glanceable signal an operator trusts to know whether 66+ tracked repos are healthy, and it encodes a non-obvious business rule (warning-severity check failures must NOT flip a repo to error state) that a passing HTTP-fragment test could easily miss if the template's Jinja conditional were reordered.

### 2. Value statement [draft]

As a Grimoire operator, I want the dashboard's status icons to be verified in a real rendered browser against known seed data, so that a broken icon or a silently-inverted health rule is caught in CI before it reaches production and misleads me about which repos actually need attention.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — reads the dashboard, trusts the icons.
- CI pipeline (system) — runs this suite on every PR; blocks merge on P0 failure.
- Playwright browser (system) — drives real Chromium against a locally-spawned instance.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e` (developer) or the `e2e` CI job (PR pipeline).
Precondition: `uv sync` has installed `pytest-playwright` and `playwright install --with-deps chromium` has run.

### 5. Main flow and business logic [draft]

1. Session-scoped fixture spawns `uvicorn grimoire.app:create_app` on an ephemeral port.
2. Test seeds the in-memory GitHub cache and a temp SQLite DB via `tests/e2e/factories.py`, mirroring `tests/test_web/conftest.py`'s `acme/api` / `acme/frontend` shapes.
3. Playwright `page.goto(base_url + "/")`.
4. Test locates each repo row and asserts the rendered health icon's CSS class and `title` attribute match the expected `health_status` (`error` / `warning` / `ok`) for that fixture.
5. Test locates per-branch workflow and check cells and asserts icon class matches `status` (`success`/`failure`/`pending` for workflows; `pass`/`fail`+`severity`/not-run for checks).
6. Test hovers a check cell and asserts the tooltip `data-tip` text.
7. Test clicks a check cell and asserts navigation to the deep-link URL.

Interruption point: N/A — each test is a single page load, no multi-step user pause.

### 6. Alternative flows and exceptions [draft]

6a. Repo has a failing workflow, no stale items → health = `error`, icon = `fa-xmark status-icon-failure` (SC-e11s02-P0-01).
6b. Repo has only stale issues/PRs, no wf/check failures → health = `warning`, icon = `fa-triangle-exclamation status-icon-pending` (SC-e11s02-P0-02).
6c. Repo is fully green → health = `ok`, icon = `fa-check status-icon-success` (SC-e11s02-P0-03).
6d. **Critical:** repo's only failure is a warning-severity check → health stays non-`error` (router.py:105 excludes warning-severity from health) (SC-e11s02-P0-04).
6e. Per-branch check cell has never run for that repo+branch → icon = `fa-minus status-icon-not-run`.

### 7. Interface elements [draft]

Context: existing (`dashboard_matrix.html`).
Static elements: repo row, health icon, workflow cell icons, check cell icons.
Dynamic elements: tooltip on hover, deep-link href assembled from check slug + result id.

### 8. Domain model [draft]

Entities read (not created): `RepoViewModel.health_status` (computed property, `router.py:104-116`), `WorkflowStatus.status`, per-branch `CheckResultRecord.passed` + `CheckDefinition.severity`. No new entities — this story only asserts existing computed state renders correctly.

### 9. Integrations and boundaries [draft]

- GitHub API — ethereal, direction: in — intercepted via `respx`; never hit live API (repo rule).
- None else; this story is purely rendering-layer verification against seeded local state.

### 10. Background processes [draft]

Not applicable — no scheduled or async processes are exercised by this story; all data is pre-seeded synchronously before page load.

### 11. Notifications [draft]

Not applicable — no notification channel is touched by icon rendering.

### 12. Audit and logging [draft]

Not applicable — this is a read-only rendering assertion; no audit trail is produced or consumed.

### 13. Solution variabilities [draft]

- `staleness.problematic_stale_issues_pct` / `problematic_stale_prs_pct` (config) — affects `(N)` badge coloring, not the health icon itself (covered in e11s03, not here).
- Check `severity` (per-check YAML field: `error` | `warning`) — directly drives icon variant and health-rule exclusion; this is the parameter under test in 6d.

### 14. Quality attributes *NFR* [draft]

- Each test in this story completes in < 3s (single page load, no polling loop).
- Suite as a whole (9 tests) completes in < 30s on CI runners.

### 15. Security and compliance *NFR* [draft]

Not applicable — no auth boundary, no PII, no external write. Read-only rendering of already-public dashboard data.

### 16. UX and accessibility *NFR* [draft]

- Every status icon carries a `title` attribute conveying pass/fail/warning semantics in text, not color alone (verified structurally here; full axe-core scan deferred to e11s10).

### 17. Acceptance criteria [draft]

```
Scenario: Failing workflow renders error health icon (SC-e11s02-P0-01)
  Given a seeded repo "acme/frontend" with a workflow status of "failure" on main
  When  the operator loads the dashboard
  Then  the repo's health icon has class "fa-xmark status-icon-failure"
  And   its title starts with "Error"

Scenario: Stale-only repo renders warning health icon (SC-e11s02-P0-02)
  Given a seeded repo with stale issues but no workflow or check failures
  When  the operator loads the dashboard
  Then  the repo's health icon has class "fa-triangle-exclamation status-icon-pending"
  And   its title starts with "Warning"

Scenario: Fully green repo renders healthy icon (SC-e11s02-P0-03)
  Given a seeded repo "acme/api" with all workflows passing and no stale items
  When  the operator loads the dashboard
  Then  the repo's health icon has class "fa-check status-icon-success"
  And   its title is "Healthy"

Scenario: Warning-severity check failure does not flip health to error (SC-e11s02-P0-04)
  Given a seeded repo "acme/warn-only" whose only failure is a check with severity "warning"
  When  the operator loads the dashboard
  Then  the repo's health icon is NOT "fa-xmark status-icon-failure"
  And   the repo's health_status is "ok" or "warning", never "error"

Scenario: Per-branch workflow and check cell icons match status (SC-e11s02-P1-05/06)
  Given a repo with a "success" workflow on main and a "fail" check with severity "warning" on develop
  When  the operator loads the dashboard
  Then  the main workflow cell shows a green check icon
  And   the develop check cell shows a yellow triangle icon, not a red X

Scenario: Check cell deep-links to the checks page (SC-e11s02-P1-07)
  Given a repo with a check result for slug "no-secrets" and result id 42
  When  the operator clicks the check cell
  Then  the browser navigates to "/checks?expand=no-secrets&result=42#check-card-no-secrets"

Scenario: Check cell tooltip shows name, branch, and status (SC-e11s02-P2-08)
  Given a repo with a check result for "Watchdog" on "main" with status "fail"
  When  the operator hovers the check cell
  Then  a tooltip appears with text "Watchdog (main): fail"
```

### 18. Out of scope [draft]

- Staleness badge coloring thresholds (e11s03).
- Full accessibility scan across the icon set (e11s10).
- Cross-browser rendering (Chromium only in v1).

### 19. Open questions [draft]

- None blocking. Confirm with the team whether `acme/warn-only`'s fixture shape should also cover the "warning check fails AND stale items present" combination, or whether that's adequately covered by 6b — owner: dvm, needed by: story kickoff.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s02.
- `src/grimoire/web/router.py:104-116` (`health_status` property).
- `src/grimoire/web/templates/partials/dashboard_matrix.html:41-101` (icon rendering).
- `tests/test_web/conftest.py` (`_populate_cache`, reused fixture shapes).
