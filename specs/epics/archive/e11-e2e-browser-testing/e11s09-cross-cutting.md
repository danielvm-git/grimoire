```
STORY KEY: e11s09
TITLE:     Cross-cutting E2E (nav, theme, responsive, a11y basics)
TYPE:      Story
PARENT:    e11-e2e-browser-testing
STATUS:    Draft
AUTHOR:    plan-work           DATE: 2026-07-30
MATURITY:  3
SIZE:      M
```

### 1. Business narrative [draft]

`base.html` provides the nav bar, theme toggle, and responsive shell shared by all 5 pages — live tour confirmed dark mode is the default and the moon/sun toggle sits top-right. These behaviors are invisible to the existing HTTP-fragment suite entirely, since they're pure client-side JS (localStorage persistence, viewport-driven layout) with no server-rendered equivalent to assert against.

### 2. Value statement [draft]

As a Grimoire operator, I want navigation, theme persistence, and small-viewport layout verified in a browser, so the shared shell around every page never silently breaks.

### 3. Actors and permissions [draft]

- Grimoire operator (external) — navigates, toggles theme, uses the app on mobile.

### 4. Trigger and preconditions [draft]

Trigger: `just test-e2e`. Precondition: e11s01 harness in place.

### 5. Main flow and business logic [draft]

1. Click each nav link (Dashboard/Backlog/Checks/Actions); assert correct route + active-link indication.
2. Click the theme toggle; assert dark↔light flips and persists (localStorage) across a subsequent navigation.
3. Resize to a 375px mobile viewport; assert nav remains usable and no horizontal body scroll appears.
4. Assert status icons carry `title`/text semantics, not color alone.
5. Click the logo; assert it returns to `/`.

Interruption point: N/A.

### 6. Alternative flows and exceptions [draft]

6a. Theme toggled, then a hard page reload (not just SPA-style nav) → theme choice still persists from localStorage.

### 7. Interface elements [draft]

Context: existing (`base.html`).
Static elements: nav links, logo.
Dynamic elements: theme toggle (moon/sun icon), active-link highlighting.

### 8. Domain model [draft]

Not applicable — theme preference is client-side localStorage only, not a server entity.

### 9. Integrations and boundaries [draft]

Not applicable — this story is purely client-side shell behavior.

### 10. Background processes [draft]

Not applicable.

### 11. Notifications [draft]

Not applicable.

### 12. Audit and logging [draft]

Not applicable.

### 13. Solution variabilities [draft]

- Theme (dark/light) — client-side preference, the parameter under test in step 2.

### 14. Quality attributes *NFR* [draft]

- Suite completes in < 15s.

### 15. Security and compliance *NFR* [draft]

Not applicable.

### 16. UX and accessibility *NFR* [draft]

- WCAG 2.1 AA baseline: status semantics not color-only (checked here structurally; full axe-core scan in e11s10).
- No horizontal scroll at 375px viewport width.

### 17. Acceptance criteria [draft]

```
Scenario: Nav links route correctly with active-state indication (SC-e11s08-P1-01)
  Given the operator is on the dashboard
  When  they click "Checks" in the nav bar
  Then  the browser navigates to "/checks"
  And   the "Checks" nav link shows an active-state indicator

Scenario: Theme toggle persists across navigation (SC-e11s08-P1-02)
  Given the app is in dark mode
  When  the operator clicks the theme toggle
  Then  the page switches to light mode
  And   navigating to a different page keeps light mode active

Scenario: Mobile viewport keeps nav usable with no horizontal scroll (SC-e11s08-P2-03)
  Given the viewport is resized to 375px wide
  When  the operator loads the dashboard
  Then  the nav bar remains usable
  And   the page body has no horizontal scrollbar

Scenario: Status icons convey semantics via text, not color alone (SC-e11s08-P2-04)
  Given the dashboard renders status icons
  When  a screen reader inspects an icon
  Then  its title/aria text conveys pass/fail/warning meaning

Scenario: Logo returns to the dashboard (SC-e11s08-P3-05)
  Given the operator is on any page
  When  they click the Grimoire logo
  Then  the browser navigates to "/"
```

### 18. Out of scope [draft]

- Full axe-core accessibility audit (e11s10).
- Page-specific content correctness (covered by e11s03-e11s08).

### 19. Open questions [draft]

None blocking.

### 20. References [draft]

- `specs/tech-architecture/e11-TEST_PLAN_LATEST.md` §s08.
- `src/grimoire/web/templates/base.html`.
