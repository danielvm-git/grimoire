```
STORY KEY: e11s06
TITLE:     Actions page E2E (run, toggle, history, output)
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  3
SIZE:      M
```

### 1. Business narrative [draft]

`/actions` mirrors the checks page's run/poll/toggle pattern but for mutating operations (`rerun-failed-pr-workflows`, generic `test`) — live tour this session confirmed the same UI shape. Because actions can have side effects on tracked repos, a stuck or silently-failing run button is worse here than on the checks page: an operator might re-click Run, unaware an action is already in flight.

### 2. Value statement [draft]

As a Grimoire operator, I want the actions page's run cycle, toggle, and history verified in a browser, so I never lose track of whether a mutating action actually completed.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — triggers actions, reviews run history.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: e11s01 harness + seeded `ActionDefinition` with a mocked fast-completing run.

### 5. Main flow and business logic [draft]

1. Load `/actions`; assert seeded action cards render.
2. Click Run; assert running state, then poll-driven return to idle; assert new run appears in history.
3. Click Toggle; assert enabled state flips and persists.
4. Click Results; assert `/partials/action-results/{slug}` lists prior runs.
5. Click a run row; assert `/partials/action-output/{result_id}` shows the full transcript.
6. Expand a run's per-repo detail; assert pass/fail icons match each repo's `passed` boolean.

Interruption point: between run-trigger and poll-resolution, same risk class as e11s05.

### 6. Alternative flows and exceptions [draft]

6a. Action run partially fails (some repos pass, some fail) → per-repo icons reflect the mixed result accurately, not a single aggregate pass/fail.
6b. Toggling a disabled action still shows its run history (history isn't hidden by disabling).

### 7. Interface elements [draft]

Context: existing (`actions.html`, `action_run_button.html`, `action_results.html`, `action_run_detail.html`).
Static elements: action card, Disable/Enable button.
Dynamic elements: Run button state machine, Results history list, per-run detail expansion.

### 8. Domain model [draft]

Reads/writes `ActionDefinition.enabled`, `ActionRunRecord`, `ActionRunRepoRecord`. No schema changes.

### 9. Integrations and boundaries [draft]

- Action execution engine — ethereal, in (mocked fast-completing run; real execution covered by `tests/test_actions/test_engine.py`).

### 10. Background processes [draft]

- Action run polling (manual+scheduled) — core process under test.

### 11. Notifications [draft]

Not applicable.

### 12. Audit and logging [draft]

`ActionRunRecord`/`ActionRunRepoRecord` already unit-tested for correctness; this story asserts the UI reflects them accurately.

### 13. Solution variabilities [draft]

None beyond what's already covered structurally by the run/toggle/results pattern.

### 14. Quality attributes *NFR* [draft]

- Suite completes in < 15s using mocked fast-completing runs.

### 15. Security and compliance *NFR* [draft]

- Mutating actions run in isolated worktrees per `docs/specs/05-actions-engine.md` — this story tests the UI layer only, not sandboxing (out of scope, covered elsewhere).

### 16. UX and accessibility *NFR* [draft]

- Per-repo pass/fail icons within a run must be distinguishable without color alone — asserted structurally.

### 17. Acceptance criteria [draft]

```
Scenario: Actions page lists all definitions (SC-e11s05-P0-01)
  Given seeded action definitions
  When  the operator loads "/actions"
  Then  one card renders per definition

Scenario: Run button completes a full cycle (SC-e11s05-P0-02)
  Given an action with a mocked fast-completing run
  When  the operator clicks "Run"
  Then  the button enters running state, then returns to idle on completion
  And   the new run appears in the results history

Scenario: Toggle persists (SC-e11s05-P0-03)
  Given an enabled action
  When  the operator clicks "Disable"
  Then  the label flips and persists across reload

Scenario: Results history and output transcript (SC-e11s05-P1-04)
  Given an action with 2 prior runs
  When  the operator clicks "Results" then a run row
  Then  the results list shows both runs
  And   clicking a row loads its full output transcript

Scenario: Per-repo icons reflect mixed pass/fail (SC-e11s05-P2-05)
  Given a run where "acme/api" passed and "acme/frontend" failed
  When  the operator expands that run's detail
  Then  "acme/api" shows a pass icon and "acme/frontend" shows a fail icon
```

### 18. Out of scope [draft]

- Real script execution / worktree sandboxing (covered by `tests/test_actions/`).

### 19. Open questions [draft]

None blocking.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s05.
- `docs/specs/05-actions-engine.md`.
