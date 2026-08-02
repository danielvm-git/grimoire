```
STORY KEY: e11s04
TITLE:     Repository detail page E2E
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  3
SIZE:      S
```

### 1. Business narrative [draft]

The repo detail page is where an operator drills in after spotting a problem on the dashboard — confirmed live at `/repo/danielvm-git/bigpowers` this session, showing header stats, per-check Output buttons, and workflow run links. It's a smaller surface than the dashboard but a dead end if broken (operator clicks through, sees nothing useful) is exactly the kind of regression only a rendered-browser test catches.

### 2. Value statement [draft]

As a Grimoire operator, I want the repository detail page's stats, output expansion, and links verified in a browser, so that drilling into a specific repo never silently fails.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — reads repo detail, expands check output.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: e11s01 harness in place.

### 5. Main flow and business logic [draft]

1. Load `/repo/{owner}/{name}` for a seeded repo.
2. Assert header, issue/PR/branch counts, and "View on GitHub" link render.
3. Click a check's "Output" button; assert the panel expands in place via `hx-get`.
4. Assert workflow run links point at the correct GitHub Actions run URL.

Interruption point: N/A.

### 6. Alternative flows and exceptions [draft]

6a. Unknown owner/name combination → `not_found.html` renders (real 404 page, not a stacktrace).

### 7. Interface elements [draft]

Context: existing (`repository.html`).
Static elements: header, counts, GitHub link.
Dynamic elements: per-check Output expand/collapse.

### 8. Domain model [draft]

Reads `RepositoryStats`, `WorkflowStatus`, per-check results for the repo. No new entities.

### 9. Integrations and boundaries [draft]

- GitHub API — ethereal, in — `respx`-mocked; link targets asserted structurally, not followed.

### 10. Background processes [draft]

Not applicable.

### 11. Notifications [draft]

Not applicable.

### 12. Audit and logging [draft]

Not applicable.

### 13. Solution variabilities [draft]

None — this page has no config-driven variability beyond what's already covered by the dashboard.

### 14. Quality attributes *NFR* [draft]

- Suite completes in < 10s.

### 15. Security and compliance *NFR* [draft]

Not applicable — read-only public data.

### 16. UX and accessibility *NFR* [draft]

Not applicable — covered by e11s10's cross-page a11y scan.

### 17. Acceptance criteria [draft]

```
Scenario: Repo detail renders header and counts (SC-e11s03-P0-01)
  Given a seeded repo "acme/api" with known issue/PR/branch counts
  When  the operator navigates to "/repo/acme/api"
  Then  the header, counts, and "View on GitHub" link render correctly

Scenario: Check output expands in place (SC-e11s03-P1-02)
  Given the repo detail page lists a check result
  When  the operator clicks that check's "Output" button
  Then  the full output panel expands via an hx-get partial swap

Scenario: Workflow run links point at GitHub Actions (SC-e11s03-P1-03)
  Given a workflow run with a known run id
  When  the operator inspects the workflow link
  Then  its href is "https://github.com/{owner}/{repo}/actions/runs/{id}"

Scenario: Unknown repo shows a real 404 (SC-e11s03-P2-04)
  Given no repo named "acme/does-not-exist" is tracked
  When  the operator navigates to "/repo/acme/does-not-exist"
  Then  a 404 page renders, not a stacktrace or blank response
```

### 18. Out of scope [draft]

- Dashboard-level sorting/navigation (e11s03).

### 19. Open questions [draft]

None blocking.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s03.
- `src/grimoire/web/router.py::repository_detail`.
