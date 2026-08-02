```
STORY KEY: e11s02
TITLE:     Live post-deploy smoke gate
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  4
SIZE:      L
```

### 1. Business narrative [draft]

`.github/workflows/deploy.yml` triggers off `workflow_run` completion of "Test Build Release" and, on success, deploys straight to `grimoire.bigbase.click` via the BigBase deploy action — with zero verification that the deployed app actually renders afterward. This session's live tour caught a real symptom of that gap: production reports `Grimoire v0.6.0` in its footer while the checked-out `main` branch's `pyproject.toml` reads `0.5.3` — a version-tracking drift that no automated check currently surfaces. A template error, a broken HTMX target, or a startup failure introduced between the unit-test pass and the deploy step would only be caught by a human clicking around, as happened this session. This story closes that gap with a read-only smoke suite gated into the deploy pipeline itself.

### 2. Value statement [draft]

As the Grimoire maintainer, I want the deploy pipeline to fail loudly if the live site doesn't actually render after deploy, so that a broken production deploy is caught by CI within minutes instead of by me noticing the dashboard looks wrong.

### 3. Actors and permissions [draft]

- Deploy pipeline (system) — runs smoke suite after the BigBase deploy step; fails the workflow on smoke failure.
- Maintainer (internal) — receives the failed-workflow notification from GitHub Actions.
- Production site (external, read-only target) — `grimoire.bigbase.click`, never mutated by this suite.

### 4. Trigger and preconditions [draft]

Trigger: the "Deploy to BigBase" step in `deploy.yml` completes.
Precondition: `SITE_URL` env (`https://grimoire.bigbase.click`) is reachable; `GRIMOIRE_EXPECTED_VERSION` is set from the release metadata already available in `deploy-meta.json`.

### 5. Main flow and business logic [draft]

1. Deploy step succeeds.
2. New `smoke` job runs `just smoke` against `SITE_URL`.
3. Suite loads `/`, `/checks`, `/actions`, `/backlog` and asserts 200 + non-empty `<title>`.
4. Suite resolves the first repo link from the live dashboard and loads its `/repo/{owner}/{name}` page.
5. Suite asserts the footer version string equals `GRIMOIRE_EXPECTED_VERSION`.
6. Suite asserts at least one status icon of each class renders (page isn't blank/erroring) and one safe `hx-get` partial (dashboard-list) returns 200.
7. If any assertion fails, the `smoke` job exits non-zero and the GitHub Actions run shows red — visible in the Actions UI and (if configured) any status-check integrations.

Interruption point: N/A — smoke runs once, immediately post-deploy, no pause/resume.

### 6. Alternative flows and exceptions [draft]

6a. Site unreachable (network/DNS/deploy failure) → smoke fails with a connection error, deploy workflow shows red.
6b. Page loads but returns non-200 (e.g. 500 from a template exception) → smoke fails on the status-code assertion.
6c. Version string mismatch (drift, like the 0.6.0-vs-0.5.3 case found this session) → smoke fails on the version assertion, surfacing drift immediately rather than silently.
6d. Console errors present on page load (JS exception breaking HTMX) → smoke fails on the no-console-errors assertion.

### 7. Interface elements [draft]

Context: existing (production pages, unmodified by this story).
Static elements: none new — this story only reads existing pages.
Dynamic elements: one safe HTMX partial fetch (`/partials/dashboard-list`) to prove partial swaps work in production, not just full-page loads.

### 8. Domain model [draft]

No new entities. Reads existing production state as a black box: HTTP status codes, `<title>`, footer version text, presence of icon CSS classes, browser console log.

### 9. Integrations and boundaries [draft]

- Production Grimoire instance (perennial, direction: in, read-only) — the smoke target itself.
- GitHub Actions `deploy.yml` (perennial, direction: both) — this story adds a job and reads its outcome to gate the workflow.

### 10. Background processes [draft]

Not applicable — smoke runs once per deploy, synchronously, not on a schedule.

### 11. Notifications [draft]

- GitHub Actions workflow failure status — recipient: repo watchers / maintainer — trigger: any smoke assertion fails. (Uses GitHub's existing notification mechanism; no new notification channel is built.)

### 12. Audit and logging [draft]

Smoke run output (pass/fail per assertion) is captured in the GitHub Actions job log — the existing CI log retention is the audit trail. No new logging destination.

### 13. Solution variabilities [draft]

- `SMOKE_BASE_URL` (config, env var) — defaults to production; can point at a staging URL for pre-prod verification.
- `GRIMOIRE_EXPECTED_VERSION` (config, sourced from `deploy-meta.json`) — parameterizes the version-drift check per deploy.

### 14. Quality attributes *NFR* [draft]

- Smoke suite completes in < 60s (6 page loads + assertions against a live network target).
- Adds < 90s to total `deploy.yml` wall-clock time (10-minute job timeout already budgeted; smoke fits comfortably inside it).

### 15. Security and compliance *NFR* [draft]

- No new secrets required — smoke reads only public, unauthenticated pages already served by the production instance.
- Never triggers `check-run`, `action-run`, `refresh-trigger`, or `save-weights` — read-only by design, enforced by code review (no POST calls in `tests/smoke/`).

### 16. UX and accessibility *NFR* [draft]

Not applicable — this story verifies operational health (deploy correctness), not end-user UX quality; UX/a11y scanning is e11s10's scope.

### 17. Acceptance criteria [draft]

```
Scenario: Core pages return 200 with a title (SC-e11s09-P0-01)
  Given the smoke suite targets SMOKE_BASE_URL
  When  it requests "/", "/checks", "/actions", and "/backlog"
  Then  each response is HTTP 200
  And   each page's <title> is non-empty

Scenario: A repo detail page renders (SC-e11s09-P0-02)
  Given the dashboard lists at least one repo
  When  the smoke suite follows the first repo link
  Then  the repository detail page returns HTTP 200

Scenario: Deployed version matches expected release (SC-e11s09-P0-03)
  Given GRIMOIRE_EXPECTED_VERSION is set from deploy-meta.json
  When  the smoke suite reads the footer version string on the live site
  Then  it equals GRIMOIRE_EXPECTED_VERSION exactly

Scenario: Status icons and a safe HTMX partial are present (SC-e11s09-P1-04/05)
  Given the live dashboard has rendered
  When  the smoke suite inspects the page
  Then  at least one icon of each rendered status class is present
  And   GET /partials/dashboard-list returns HTTP 200

Scenario: No console errors on core page loads (SC-e11s09-P2-06)
  Given the smoke suite loads each of the 5 core pages
  When  it inspects the browser console
  Then  no error-level console messages are recorded

Scenario: Smoke failure blocks the deploy workflow from reporting success (6a-6d)
  Given any smoke assertion fails
  When  the "smoke" job in deploy.yml runs
  Then  the job exits non-zero
  And   the GitHub Actions run for this deploy shows a failed status
```

### 18. Out of scope [draft]

- Automated rollback on smoke failure (out of scope for v1 — manual intervention after a red smoke gate).
- Synthetic monitoring / continuous post-deploy polling (this runs once, immediately post-deploy, not on a recurring schedule).
- Mutating smoke checks (run a real check/action against prod) — deliberately excluded per repo rule against touching production state from tests.

### 19. Open questions [draft]

- Should a failed smoke gate also auto-open a GitHub issue, or is the red Actions run sufficient signal for a solo maintainer? — owner: dvm, needed by: story kickoff. Current plan assumes the red run is sufficient (matches existing "Never work directly on main" / CI-driven workflow conventions already in this repo).

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s09.
- `.github/workflows/deploy.yml` (existing deploy pipeline, to be extended).
- Live tour finding this session: production footer read "Grimoire v0.6.0" vs. local `pyproject.toml` "0.5.3".
