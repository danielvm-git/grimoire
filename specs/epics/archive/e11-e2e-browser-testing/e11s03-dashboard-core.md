```
STORY KEY: e11s03
TITLE:     Dashboard core E2E (sort, totals, view toggle)
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  3
SIZE:      M
```

### 1. Business narrative [draft]

The dashboard is the first screen every operator sees and the one they sort most: by health when triaging, by failing-workflows when firefighting, by last-activity when auditing stale repos. Session's live tour confirmed 9 independent sort dimensions plus a matrix/list toggle, all HTMX-driven — none of it exercised in a real browser today. A regression in the sort-direction toggle (e.g. re-clicking "Name" not flipping asc/desc) would ship silently.

### 2. Value statement [draft]

As a Grimoire operator, I want dashboard sorting, totals, and view switching verified in a real browser, so that the primary triage screen never silently breaks its core interaction.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — sorts, switches views, reads totals.
- CI pipeline (system) — runs this suite on every PR.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: e11s01's harness (uvicorn fixture, factories) is in place.

### 5. Main flow and business logic [draft]

1. Load dashboard with a multi-repo seeded fixture set (mixed health/issue/PR/branch counts).
2. Assert the 5 summary tiles match computed totals exactly.
3. Click each of the 9 sort headers in turn; assert the matrix partial swaps, row order changes, and the ▲/▼ indicator moves to the clicked column.
4. Re-click the active sort header; assert direction flips.
5. Toggle matrix ↔ list view; assert the sort persists across the swap.
6. Assert stale-count badges color `text-warning` only above the configured threshold.

Interruption point: N/A.

### 6. Alternative flows and exceptions [draft]

6a. Sorting by a column with all-equal values → order is stable, no crash.
6b. Zero repos seeded → summary tiles show 0 without division-by-zero errors (staleness % calc guards `open_issues > 0`).

### 7. Interface elements [draft]

Context: existing (`dashboard.html`, `dashboard_matrix.html`, `dashboard_list.html`).
Static elements: 5 summary tiles, matrix/list toggle buttons.
Dynamic elements: 9 sort-header buttons with HTMX swap + direction indicator.

### 8. Domain model [draft]

Reads `DashboardTotals` (computed in `_compute_totals`) and `RepoViewModel` sort keys (`SORT_KEYS` dict in `router.py:209`). No new entities.

### 9. Integrations and boundaries [draft]

- GitHub API — ethereal, in — `respx`-mocked.

### 10. Background processes [draft]

Not applicable.

### 11. Notifications [draft]

Not applicable.

### 12. Audit and logging [draft]

Not applicable — read-only rendering assertions.

### 13. Solution variabilities [draft]

- `staleness.problematic_stale_issues_pct` / `problematic_stale_prs_pct` (config) — drives badge coloring threshold under test.

### 14. Quality attributes *NFR* [draft]

- Suite completes in < 20s.

### 15. Security and compliance *NFR* [draft]

Not applicable.

### 16. UX and accessibility *NFR* [draft]

- Sort direction is conveyed by both an arrow glyph and (implicitly) column position — full a11y scan deferred to e11s10.

### 17. Acceptance criteria [draft]

```
Scenario: Summary tiles match seeded totals (SC-e11s01-P0-01/02)
  Given a seeded fixture set with known issue/PR/workflow/check counts
  When  the operator loads the dashboard
  Then  each of the 5 summary tiles shows the exact computed total
  And   the breakdown text shows the correct failing/warning/healthy split

Scenario: Sorting by a column reorders rows and toggles direction (SC-e11s01-P1-03/04)
  Given the dashboard is loaded with unsorted repos
  When  the operator clicks the "Failing Workflows" sort header
  Then  rows reorder by failing-workflow count
  And   the header shows a descending indicator
  When  the operator clicks the same header again
  Then  the order reverses and the indicator flips to ascending

Scenario: View toggle preserves the active sort (SC-e11s01-P1-05)
  Given the dashboard is sorted by "Health" descending
  When  the operator switches from Matrix to List view
  Then  the List view renders the same repos in the same sorted order

Scenario: Stale badge coloring respects the configured threshold (SC-e11s01-P2-06)
  Given a repo with stale-issue percentage above problematic_stale_issues_pct
  When  the operator loads the dashboard
  Then  the stale count badge has class "text-warning"
  And   a repo below the threshold shows class "opacity-50" instead

Scenario: Repo name navigates to detail page (SC-e11s01-P2-07)
  Given the dashboard lists "acme/api"
  When  the operator clicks the repo name
  Then  the browser navigates to "/repo/acme/api"
```

### 18. Out of scope [draft]

- Repo detail page content (e11s04).
- Status icon semantics (e11s01).

### 19. Open questions [draft]

None blocking.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s01.
- `src/grimoire/web/router.py` (`_compute_totals`, `SORT_KEYS`, `_build_sorted_repos`).
