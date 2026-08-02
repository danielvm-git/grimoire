```
STORY KEY: e11s08
TITLE:     Refresh & loading flow E2E
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  3
SIZE:      S
```

### 1. Business narrative [draft]

Every page's data currency depends on the refresh cycle — live tour showed "Last updated 3m ago" and a "Scheduled: */30 * * * *" label, both driven by the same manual-trigger + polling pattern used by checks/actions. The cold-start loading page (`loading.html`) is a special case: it's the very first thing a user sees on a fresh instance with no cached data yet, and a broken poller there would leave the app looking permanently stuck.

### 2. Value statement [draft]

As a Grimoire operator, I want the manual refresh cycle and cold-start loading page verified in a browser, so a fresh instance never appears stuck and a manual refresh always visibly completes.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — triggers manual refresh, waits through cold-start.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: e11s01 harness, with a mocked GitHub fetch that resolves quickly for the refresh/cold-start scenarios.

### 5. Main flow and business logic [draft]

1. Click Refresh; assert button enters running state.
2. Poll (`/partials/refresh-status?was_running=1`) resolves; assert idle state + updated "Last updated" text.
3. Simulate cold start (empty cache); assert `loading.html` renders and polls `/partials/loading-status` until it auto-replaces itself with the dashboard.
4. Assert the scheduled-refresh cron label renders correctly from config.

Interruption point: between refresh-trigger and status-resolution — same class of risk as the check/action pollers.

### 6. Alternative flows and exceptions [draft]

6a. GitHub fetch fails mid-refresh → refresh status reflects failure, not a stuck running state.
6b. Cold start with zero configured repos → loading page still resolves to a (empty) dashboard, not an infinite poll.

### 7. Interface elements [draft]

Context: existing (`refresh_button.html`, `loading.html`, `loading_progress.html`).
Static elements: Refresh button, "Scheduled: ..." label.
Dynamic elements: refresh status poller, cold-start loading poller.

### 8. Domain model [draft]

Not applicable — no new entities; reads existing refresh-state signals.

### 9. Integrations and boundaries [draft]

- GitHub API — ethereal, in — `respx`-mocked with a controllable resolve delay.

### 10. Background processes [draft]

- Manual refresh trigger → GitHub fetch → cache update (manual+scheduled) — the process under test.
- Cold-start initial fetch (scheduled: on app startup with empty cache) — the process under test.

### 11. Notifications [draft]

Not applicable.

### 12. Audit and logging [draft]

Not applicable.

### 13. Solution variabilities [draft]

- Refresh schedule cron expression (config, `set_refresh_schedule`) — drives the label text asserted in this story.

### 14. Quality attributes *NFR* [draft]

- Suite completes in < 10s using a mocked fast-resolving fetch.

### 15. Security and compliance *NFR* [draft]

Not applicable.

### 16. UX and accessibility *NFR* [draft]

- Loading state must be visually and textually distinguishable from idle (spinner + text), not color alone.

### 17. Acceptance criteria [draft]

```
Scenario: Manual refresh completes a full cycle (SC-e11s07-P0-01/02)
  Given the dashboard is loaded
  When  the operator clicks "Refresh"
  Then  the button enters a running state
  And   once the (mocked) fetch completes, the button returns to idle
  And   "Last updated" reflects the new timestamp

Scenario: Cold start auto-replaces the loading page (SC-e11s07-P1-03)
  Given a fresh instance with no cached data
  When  the operator loads "/"
  Then  loading.html renders and polls loading-status
  And   once the initial fetch completes, the dashboard replaces the loading page automatically

Scenario: Scheduled refresh label renders from config (SC-e11s07-P2-04)
  Given a refresh schedule of "*/30 * * * *"
  When  the operator loads the dashboard
  Then  the label reads "Scheduled: */30 * * * *"
```

### 18. Out of scope [draft]

- The actual GitHub fetch/cache-update logic correctness (covered by `tests/test_github/`).

### 19. Open questions [draft]

None blocking.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s07.
- `src/grimoire/web/templates/partials/refresh_button.html`, `loading.html`.
