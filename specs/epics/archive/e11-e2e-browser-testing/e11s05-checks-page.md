```
STORY KEY: e11s05
TITLE:     Checks page E2E (run, toggle, results, output, deep-link)
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  4
SIZE:      L
```

### 1. Business narrative [draft]

Live tour of `/checks` this session showed 11 check definitions (license-exists, ci-cd-pipeline-audit, no-secrets, lint-passes, etc.), each with Run, Disable, Script, and Results controls — an async run→poll→complete cycle mediated entirely by HTMX polling (`hx-get .../check-run-status/{slug}?was_running=1`). This is the most stateful, most failure-prone interaction in the app: a broken poller would leave the Run button stuck "running" forever with no browser test to catch it.

### 2. Value statement [draft]

As a Grimoire operator, I want the checks page's run/toggle/results/output cycle verified end-to-end in a browser, so that a broken poller or a silently-failing toggle never strands an operator mid-workflow.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — runs checks, toggles them, reviews output.
- Check scheduler (system, out of scope here) — the actual bash execution is mocked; this story tests the UI cycle, not the execution engine (already covered by `tests/test_checks/`).

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: e11s01 harness + at least one seeded `CheckDefinition` with a mocked-fast-completing run.

### 5. Main flow and business logic [draft]

1. Load `/checks`; assert all seeded check cards render.
2. Click Run on a card; assert button enters running state.
3. Poll (`check-run-status`) resolves (mocked to complete quickly); assert button returns to idle.
4. Click Toggle; assert label flips Enable↔Disable and persists across reload.
5. Click Results; assert `/partials/check-results/{slug}` loads with pass/fail/warning counts.
6. Click a result row; assert `/partials/check-output/{id}` shows full output, with a truncation banner when output exceeds 64KB.
7. Navigate directly to a deep-link URL (`?expand={slug}&result={id}#check-card-{slug}`); assert the card auto-expands without a click.
8. Click Script; assert the check's bash source is revealed.

Interruption point: between steps 2 and 3 (running state visible, poll not yet resolved) — this is the state most likely to break silently.

### 6. Alternative flows and exceptions [draft]

6a. Check run fails (non-zero exit) → run status reflects failure, not stuck "running".
6b. Output exceeds the 64KB truncation cap → banner shown, output visibly truncated (not silently cut with no indication).
6c. Toggling a check that's mid-run → toggle still succeeds; running state is unaffected (definition enabled/disabled is independent of an in-flight run).

### 7. Interface elements [draft]

Context: existing (`checks.html`, `check_run_button.html`, `check_results.html`, `check_output.html`).
Static elements: check card, Disable/Enable button, Script button.
Dynamic elements: Run button (state machine: idle → running → idle), Results panel, Output panel, deep-link auto-expand JS.

### 8. Domain model [draft]

Reads/writes `CheckDefinition.enabled` (toggle), `CheckRunRecord`, `CheckResultRecord`. No schema changes — this story exercises existing persistence via the UI.

### 9. Integrations and boundaries [draft]

- Check execution engine — ethereal, in (mocked to complete fast/deterministically for this story; real bash execution already covered by `tests/test_checks/test_engine.py`).

### 10. Background processes [draft]

- Check run polling (manual+scheduled: user-triggered, then polls until complete) — this is the core process under test in step 2-3.

### 11. Notifications [draft]

Not applicable — Grimoire has no notification channel for check completion beyond the UI itself.

### 12. Audit and logging [draft]

`CheckRunRecord` captures `triggered_by`, `started_at`, `finished_at` — already covered by existing unit tests; this story only asserts the UI reflects that record correctly, not that it's written correctly.

### 13. Solution variabilities [draft]

- Check `severity` (error/warning) — affects Results panel's aggregate icon (checked here); affects health computation (covered in e11s01).
- Output truncation cap (64KB, project-wide constant per CLAUDE.md) — drives the truncation-banner scenario.

### 14. Quality attributes *NFR* [draft]

- Run→poll→complete cycle test completes in < 5s using a mocked fast-resolving check (no real bash execution, no real polling interval wait).

### 15. Security and compliance *NFR* [draft]

- Not applicable for this story's scope (UI cycle only). Check scripts execute in git worktrees per `docs/specs/04-checks-engine.md` — sandboxing is that module's concern, not this story's.

### 16. UX and accessibility *NFR* [draft]

- Run button's running/idle states must be distinguishable without color alone (e.g. spinner + text change) — asserted structurally here.

### 17. Acceptance criteria [draft]

```
Scenario: Checks page lists all definitions (SC-e11s04-P0-01)
  Given 11 seeded check definitions
  When  the operator loads "/checks"
  Then  11 check cards render, one per definition

Scenario: Run button completes a full cycle (SC-e11s04-P0-02)
  Given a check definition with a mocked fast-completing run
  When  the operator clicks "Run"
  Then  the button enters a running state
  And   once the run completes, the button returns to idle
  And   the new result appears without a manual page reload

Scenario: Toggle persists across reload (SC-e11s04-P0-03)
  Given an enabled check definition
  When  the operator clicks "Disable"
  Then  the label flips to "Enable"
  And   reloading the page still shows "Enable"

Scenario: Results panel shows aggregate counts (SC-e11s04-P1-04)
  Given a check with 3 passing and 1 warning-severity failing result
  When  the operator clicks "Results"
  Then  the panel shows "3" next to a pass icon and "1" next to a warning icon

Scenario: Output panel shows full text with truncation banner (SC-e11s04-P1-05)
  Given a check result whose output exceeds the 64KB cap
  When  the operator clicks that result row
  Then  the output panel shows the truncated text
  And   a truncation banner is visible

Scenario: Deep-link auto-expands the targeted card (SC-e11s04-P1-06)
  Given a check "no-secrets" with result id 42
  When  the operator navigates directly to "/checks?expand=no-secrets&result=42#check-card-no-secrets"
  Then  the "no-secrets" card is already expanded on page load, with no click required

Scenario: Script button reveals check source (SC-e11s04-P2-07)
  Given a check definition with a known bash script
  When  the operator clicks "Script"
  Then  the script's source text is displayed
```

### 18. Out of scope [draft]

- Real bash execution correctness (covered by `tests/test_checks/test_engine.py`).
- Health-icon rule interaction with checks (e11s01).

### 19. Open questions [draft]

- Confirm the mocked-check-completion mechanism (fake clock vs. genuinely fast script) with the team before implementation — owner: dvm, needed by: story kickoff.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s04.
- `src/grimoire/web/templates/checks.html`, `partials/check_run_button.html`.
- `docs/specs/04-checks-engine.md`.
