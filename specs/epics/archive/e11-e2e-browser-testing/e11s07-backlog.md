```
STORY KEY: e11s07
TITLE:     Backlog E2E (scoring, filters, export, save-weights)
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  4
SIZE:      L
```

### 1. Business narrative [draft]

Live tour showed `/backlog` prioritizing 163 items across 60 repos by a weighted score (100 for failing workflows, 80 for critical check failures, 30 for minor ones). This is the epic's most business-logic-heavy page: score-tier ordering, filters, and a save-weights endpoint that already has a validation guard in `tests/test_web/test_router.py` (`TestBacklogSaveWeightsValidation`) but has never been exercised through a real form interaction in a browser.

### 2. Value statement [draft]

As a Grimoire operator, I want the backlog's scoring, filtering, export, and weight-saving verified in a browser, so that my prioritized triage list never silently misorders or loses a saved customization.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — reviews backlog, adjusts weights, exports.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: e11s01 harness + seeded backlog items spanning all three score tiers.

### 5. Main flow and business logic [draft]

1. Load `/backlog`; assert header summary text matches seeded item/repo/critical counts exactly.
2. Assert items render sorted by score descending, each with score badge + repo + reason.
3. Adjust a weight and save; assert `/api/backlog/save-weights` persists and reload reflects new scoring.
4. Submit an invalid weights payload; assert 4xx response (browser-level exercise of the existing `TestBacklogSaveWeightsValidation` guard).
5. Click Export; assert a file download triggers with scores/statuses/links.
6. Use the Filters panel; assert the list narrows via `/partials/backlog-items` without a full reload.
7. Assert score-tier ordering: 100 (workflow-fail) > 80 (check-fail-critical) > 30 (check-fail-minor).

Interruption point: between weight adjustment and save-confirmation — the point where an operator might navigate away before the save completes.

### 6. Alternative flows and exceptions [draft]

6a. Save-weights called with a malformed payload (out-of-range weight, missing field) → 4xx, no partial/corrupt persistence.
6b. Filters narrow the list to zero results → empty state renders, not a broken/blank panel.
6c. Export with zero backlog items → download still succeeds with an empty (not malformed) file.

### 7. Interface elements [draft]

Context: existing (`backlog.html`, `partials/backlog_items.html`).
Static elements: header summary, Export button, Filters panel toggle.
Dynamic elements: score-ordered item list, weight-adjustment controls, filter-driven partial reload.

### 8. Domain model [draft]

Reads/writes backlog scoring weights (persisted config, per `backlog.py`). Reads `BacklogItem`-shaped aggregates derived from check/workflow/PR failures across tracked repos. No new entities.

### 9. Integrations and boundaries [draft]

- GitHub API — ethereal, in — `respx`-mocked source data for backlog items.

### 10. Background processes [draft]

Not applicable — backlog scoring recomputes on read from already-cached data, not on a separate schedule.

### 11. Notifications [draft]

Not applicable.

### 12. Audit and logging [draft]

Not applicable — weight changes are user preference, not an audited business event.

### 13. Solution variabilities [draft]

- Score-tier weights (100/80/30 defaults) — the parameter this story's save-weights scenario directly mutates and re-verifies.

### 14. Quality attributes *NFR* [draft]

- Suite completes in < 20s.

### 15. Security and compliance *NFR* [draft]

- Save-weights validation (existing guard) must reject malformed input at the API boundary — this story adds browser-level coverage of that boundary, not new security controls.

### 16. UX and accessibility *NFR* [draft]

- Filters panel must remain keyboard-operable (structurally checked; full scan in e11s10).

### 17. Acceptance criteria [draft]

```
Scenario: Header summary matches seeded counts (SC-e11s06-P0-01)
  Given 163 seeded backlog items across 60 repos, 56 flagged critical
  When  the operator loads "/backlog"
  Then  the header reads "163 items across 60 repos — 56 critical · 107 other"

Scenario: Items render score-ordered with reason text (SC-e11s06-P0-02)
  Given backlog items with distinct scores
  When  the operator loads "/backlog"
  Then  items render sorted by score descending
  And   each row shows its score badge, repo, and failing-reason text

Scenario: Save-weights persists a valid change (SC-e11s06-P1-03a)
  Given the operator adjusts a scoring weight
  When  they save
  Then  POST /api/backlog/save-weights succeeds
  And   reloading the page reflects the new scoring order

Scenario: Save-weights rejects an invalid payload (SC-e11s06-P1-03b)
  Given a malformed weights payload (out-of-range value)
  When  it is submitted
  Then  the API responds with a 4xx status
  And   no partial state is persisted

Scenario: Export downloads a file with full data (SC-e11s06-P1-04)
  Given the backlog has seeded items
  When  the operator clicks "Export"
  Then  a file downloads containing scores, statuses, and links for those items

Scenario: Filters narrow the list without a full reload (SC-e11s06-P1-05)
  Given the Filters panel is open
  When  the operator applies a filter
  Then  the item list updates via a partial swap, not a full page navigation

Scenario: Score tiers render in correct order (SC-e11s06-P2-06)
  Given items scored 100 (workflow-fail), 80 (check-fail-critical), and 30 (check-fail-minor)
  When  the operator loads "/backlog"
  Then  the 100-tier items appear before the 80-tier items, which appear before the 30-tier items
```

### 18. Out of scope [draft]

- Backlog scoring algorithm correctness at the unit level (already covered elsewhere; this story verifies the browser renders the algorithm's output correctly).

### 19. Open questions [draft]

- Confirm the exact save-weights UI affordance (drag-reorder vs. numeric input) with current template before writing selectors — owner: dvm, needed by: story kickoff.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s06.
- `tests/test_web/test_router.py::TestBacklogSaveWeightsValidation` (existing guard being extended to browser level).
- `src/grimoire/web/backlog.py`.
