```
STORY KEY: e11s10
TITLE:     NFR verification (perf, a11y scan, visual regression)
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  3
SIZE:      M
```

### 1. Business narrative [draft]

The functional stories (e11s01-e11s09) prove the app behaves correctly; this story proves it behaves *well* — fast enough, accessible enough, and visually stable enough that a CSS regression doesn't silently ship. It runs last deliberately: it depends on the pages built out by earlier stories being stable enough to snapshot and profile meaningfully.

### 2. Value statement [draft]

As the Grimoire maintainer, I want automated performance, accessibility, and visual-regression guardrails, so that non-functional quality degrades loudly (a failing test) instead of silently (a slow, inaccessible, or visually broken dashboard nobody notices until a user complains).

### 3. Actors and permissions [draft]

- CI pipeline (system) — runs NFR checks on every PR; P2-tier, non-blocking initially per the test plan's rollout guidance.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: all of e11s01-e11s09 complete (stable page structure to snapshot/profile against); `axe-playwright-python` and Playwright tracing available.

### 5. Main flow and business logic [draft]

1. Load the dashboard with a representative seeded fixture set; capture a Playwright trace; assert first-contentful-paint < 1.5s.
2. Run an axe-core scan against each of the 5 core pages; assert 0 serious/critical violations.
3. Capture visual regression snapshots of the dashboard (light + dark) and one repo detail page; on first run, bless as baseline; on subsequent runs, diff and fail on unintended changes.

Interruption point: N/A.

### 6. Alternative flows and exceptions [draft]

6a. A visual snapshot diff is intentional (a real UI change) → developer runs `pytest --update-snapshots` to re-bless, not treated as a silent pass.
6b. Axe-core flags a violation below "serious" (minor/moderate) → logged but does not fail the suite (only serious/critical block).

### 7. Interface elements [draft]

Context: existing (all 5 core pages, unmodified by this story).
Static/Dynamic elements: N/A — this story observes rendered output, it does not interact with new elements.

### 8. Domain model [draft]

Not applicable — this story profiles rendering performance and accessibility tree structure, not business entities.

### 9. Integrations and boundaries [draft]

- `axe-playwright-python` — ethereal, in — third-party a11y scanning library, [OK] tagged (mature, actively maintained, npm-backed axe-core port).

### 10. Background processes [draft]

Not applicable.

### 11. Notifications [draft]

Not applicable.

### 12. Audit and logging [draft]

Playwright trace files and visual-diff artifacts are retained as CI job artifacts for post-hoc review — not a business audit trail, but useful for debugging NFR regressions.

### 13. Solution variabilities [draft]

- FCP threshold (1.5s), axe severity gate (serious/critical only) — both are configurable constants in `tests/e2e/test_nfr.py`, tunable if they prove too strict/loose in practice.

### 14. Quality attributes *NFR* [draft]

- Dashboard FCP < 1.5s on the seeded Layer-A instance (this IS the NFR under test; see also §15/§16).
- Suite (perf + a11y + visual) completes in < 30s.

### 15. Security and compliance *NFR* [draft]

Not applicable — no security-relevant behavior in this story.

### 16. UX and accessibility *NFR* [draft]

- WCAG level: AA (axe-core "serious"/"critical" rule set maps to this).
- i18n: not applicable — Grimoire is English-only today.
- Visual baseline: dashboard (light+dark), one repo detail page.

### 17. Acceptance criteria [draft]

```
Scenario: Dashboard first-contentful-paint under budget (SC-e11s10-P1-01)
  Given a seeded Layer-A instance
  When  the operator loads the dashboard
  Then  first-contentful-paint is under 1.5 seconds

Scenario: Zero serious/critical accessibility violations (SC-e11s10-P2-02)
  Given the 5 core pages (Dashboard, Repo Detail, Checks, Actions, Backlog)
  When  an axe-core scan runs against each
  Then  no serious or critical violations are reported

Scenario: Visual regression detects unintended layout changes (SC-e11s10-P2-03)
  Given a blessed baseline snapshot of the dashboard in light and dark mode
  When  the suite re-runs against the current build
  Then  it reports zero diff if nothing changed
  And   it fails with a visible diff if an unintended change was introduced
```

### 18. Out of scope [draft]

- Cross-browser visual regression (Chromium only in v1).
- Load/stress testing (separate NFR epic per the test plan's Out of Scope §5).

### 19. Open questions [draft]

- Confirm FCP budget (1.5s) is realistic for CI runner hardware, not just local dev — owner: dvm, needed by: story kickoff, adjust if CI runners prove consistently slower.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s10, §3 (NFR Verification table).
- `axe-playwright-python` package.
