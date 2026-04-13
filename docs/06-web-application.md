# Module 6: Web Application (Dashboard, Repo Detail, Actions Page)

Build the HTMX-powered web frontend with three pages: dashboard overview, individual repository detail, and actions management.

**Dependencies:** Modules 1–5 (all backend services).

## 6.1 — Application Wiring

**File:** `src/grimoire/app.py`

Update `create_app()` to:

- Mount all API routers (checks, actions, repos).
- Mount web router for HTML pages.
- Mount static files at `/static`.
- Set up Jinja2 template environment.
- Initialize on startup: database, workspace, scheduler, GitHub client, initial data load from cache.
- Register shutdown hooks: close scheduler, close HTTP clients.

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    config = load_config()
    engine = await get_engine(config.database_path)
    await create_tables(engine)
    # Load cached data from DB (instant, no API calls)
    # Initialize GitHub client, workspace manager, scheduler
    # Start background refresh task
    yield
    # Shutdown: close scheduler, close HTTP clients

def create_app() -> FastAPI:
    app = FastAPI(
        title="Grimoire",
        description="GitHub repository monitoring dashboard",
        lifespan=lifespan,
    )

    # Mount routers
    app.include_router(checks_router, prefix="/api")
    app.include_router(actions_router, prefix="/api")
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory="..."), name="static")

    return app
```

## 6.2 — Dashboard Page

**Route:** `GET /`
**Template:** `templates/dashboard.html`

### Layout

**Header area:**
- "Grimoire" title/logo.
- "Last updated: X minutes ago" timestamp (from the latest `fetched_at`).
- Manual "Refresh" button.
- Global warning banner (if applicable): rate limit warning, degraded mode notice.

**Repository table** — one row per tracked repository:

| Column | Content | Sortable? |
|--------|---------|-----------|
| **Repository** | Name as link to detail page | ✓ (alphabetical) |
| **Issues** | Open count + stale count, e.g., `12 (3 stale)` | ✓ (by open, by stale) |
| **Pull Requests** | Open count + stale count, e.g., `5 (1 stale)` | ✓ (by open, by stale) |
| **Last Activity** | Time since last commit across observed branches, e.g., `3d ago` | ✓ (by last commit time) |
| **Branches** | Total count + stale count with link to GitHub branches page | — |
| **Workflows** | Compact badge grid (see below) | ✓ (by number of failures) |
| **Checks** | Compact badge grid (see below) | ✓ (by number of failures) |

**Staleness highlighting:** Stale issue/PR counts are highlighted in yellow only when the stale percentage (stale/open) meets or exceeds the configured thresholds (`staleness.problematic_stale_issues_pct`, `staleness.problematic_stale_prs_pct`). Below the threshold, stale counts render without warning color.

**Per-repo warnings:** If a repo has warnings (e.g., "Data is 2h stale"), show an amber ⚠ icon in the row. Hover/click reveals the warning text.

### Workflow visualization (compact)

For each repo, show workflow statuses as a grid of small colored dots/badges:

```
● ● ●      (single branch — just dots)

main:    ● ● ●
develop: ● ●        (multi-branch — grouped with labels)
```

Colors: 🟢 success, 🔴 failure, 🟡 pending, ⚪ unknown.

Each dot represents one workflow. Hover shows the workflow name. Click links to the GitHub run.

When a repo has a single observed branch, omit the branch label for compactness.

### Check visualization (compact)

Same visual style as workflows: colored dots, one per applicable check.

Colors: 🟢 pass, 🔴 fail, ⚪ not yet run.

Hover shows the check name + description. For multi-branch repos, show per-branch results grouped with branch labels (same pattern as workflows).

### Sorting (HTMX)

Clicking a column header triggers an HTMX request that re-renders just the table body:

```html
<th hx-get="/partials/dashboard-table?sort=issues&dir=desc"
    hx-target="#repo-table-body"
    hx-swap="innerHTML">
  Issues ▼
</th>
```

The server sorts the data and returns the `<tbody>` HTML fragment. No full page reload.

Supported sort keys: `name`, `issues`, `stale_issues`, `prs`, `stale_prs`, `workflow_failures`, `check_failures`, `last_activity`.

### Refresh (HTMX)

The "Refresh" button triggers an API call and then re-fetches the table:

```html
<button hx-post="/api/refresh"
        hx-target="#repo-table-body"
        hx-swap="innerHTML"
        hx-indicator="#refresh-spinner">
  Refresh
</button>
```

## 6.3 — Repository Detail Page

**Route:** `GET /repo/{owner}/{name}`
**Template:** `templates/repository.html`

### Sections

**1. Header**
- Repository full name (e.g., `lucabello/grimoire`).
- Link to GitHub: `https://github.com/{owner}/{name}`.
- Default branch name.
- Source: "static" or "team: org/team-name".
- Observed branches list.
- Warning banner if any warnings exist.

**2. Stats Grid**
- Open issues, stale issues, open PRs, stale PRs.
- Stale counts are color-coded based on percentage thresholds (yellow when stale/open ≥ configured %; green otherwise). Percentage is shown as "X% of open".
- Last Activity: time since last commit across observed branches, with absolute timestamp.
- Branches: total count with link to stale branches on GitHub if any are stale.

**3. Issues**
- Total open issues count.
- **Stale issues table** (issues with no comments in `staleness.issues_days`):

| Title | # | Last Activity | Age | Link |
|-------|---|---------------|-----|------|

**3. Pull Requests**
- Total open PR count.
- **Stale PRs table** (PRs with no pushes or comments in `staleness.pull_requests_days`):

| Title | # | Author | Last Activity | Age | Link |
|-------|---|--------|---------------|-----|------|

**4. Workflows**
- Expanded table — one row per workflow × branch combination:

| Workflow | Branch | Status | Last Run | Link |
|----------|--------|--------|----------|------|

**5. Checks**
- Expanded table — one row per check × branch:

| Check | Description | Branch | Status | Last Run | Output |
|-------|-------------|--------|--------|----------|--------|

The "Output" column has an expandable/collapsible section (HTMX `hx-get` to fetch the full output on demand, to keep the initial page load light).

## 6.4 — Actions Page

**Route:** `GET /actions`
**Template:** `templates/actions.html`

### Layout

**Section 1: Available Actions**

A card or table for each defined action:

| Name | Description | Targets | Schedule | |
|------|-------------|---------|----------|----|
| Update UV Lock | Updates uv.lock and opens a PR | 12 repos (regex: `lucabello/.*`) | Mon 00:00 | [Run] |

The "Run" button triggers the action via HTMX:

```html
<button hx-post="/api/actions/update-uv-lock/run"
        hx-target="#run-history"
        hx-swap="afterbegin">
  Run
</button>
```

**Section 2: Run History**

Reverse-chronological list of all action runs (across all actions):

| Action | Triggered By | Started | Duration | Result | |
|--------|-------------|---------|----------|--------|----|
| Update UV Lock | cron | 2025-04-10 00:00 | 3m 12s | 10/12 passed | [Details] |

Clicking "Details" expands the run inline (HTMX partial):

```
┌─────────────────────────────────────────────────────┐
│ lucabello/grimoire (main)        ✅ passed           │
│ ┌─── Output ──────────────────────────────────────┐ │
│ │ Resolving dependencies...                       │ │
│ │ uv.lock is up to date.                          │ │
│ └─────────────────────────────────────────────────┘ │
│ lucabello/other-repo (main)      ❌ failed           │
│ ┌─── Output ──────────────────────────────────────┐ │
│ │ error: pyproject.toml not found                 │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

HTMX partial endpoint: `GET /partials/action-run/{run_id}`

## 6.5 — Styling

**Framework:** Tailwind CSS (via CDN for development, standalone CLI for production build) + DaisyUI for component classes.

**Design principles:**
- **Compact and data-dense** — dashboard is a control panel, not a marketing page.
- **Color-coded status** — green/red/yellow/gray consistently across all status indicators.
- **Monospace for counts** — numbers in the table use monospace font for alignment.
- **Dark mode** — DaisyUI theme support. Default to system preference.
- **Responsive** — table scrolls horizontally on small screens; key info visible on mobile.

**Template hierarchy:**
- `base.html` — HTML shell, nav bar, Tailwind/DaisyUI CDN links, HTMX script tag.
- `dashboard.html` extends `base.html`.
- `repository.html` extends `base.html`.
- `actions.html` extends `base.html`.

## 6.6 — HTMX Partial Endpoints

These endpoints return HTML fragments (not full pages) for HTMX to swap in:

| Endpoint | Returns |
|----------|---------|
| `GET /partials/dashboard-table?sort=...&dir=...` | `<tbody>` of the dashboard table |
| `GET /partials/action-run/{run_id}` | Expanded action run details |
| `GET /partials/check-output/{result_id}` | Expanded check output text |

## 6.7 — Empty States

Every section must render a helpful message when there's no data:

| Situation | Message |
|-----------|---------|
| No repos configured | "No repositories configured — edit `config.yaml` to get started." |
| First startup, no cache | Dashboard shows repos with "Loading..." spinners; data populates as the first refresh completes. |
| No checks defined | Checks column on dashboard is hidden. Repo detail shows "No checks defined." |
| No actions exist | Actions page shows "No actions defined — add YAML files to `data/actions/`." |
| No action runs yet | Run history section shows "No runs yet." |
| Repo has warnings | Amber ⚠ with hover text; never an empty row. |

## Acceptance Criteria

- [ ] Dashboard renders all tracked repos with correct stats
- [ ] Sorting works for all columns (name, issues, stale issues, PRs, stale PRs, workflow failures, check failures)
- [ ] Multi-branch repos show per-branch workflow/check status in a single row
- [ ] Per-repo warnings display as amber indicators with hover text
- [ ] Global warning banner appears when in degraded mode or rate-limited
- [ ] Repository detail page shows stale issues/PRs, workflow table, check results
- [ ] Check output is expandable on the detail page
- [ ] Actions page lists all available actions with run buttons
- [ ] Run history shows all runs with correct metadata
- [ ] Action run details expand inline with per-repo results and logs
- [ ] HTMX partial updates work without full page reloads
- [ ] Pages render correctly in both light and dark mode
- [ ] Pages are responsive (usable on tablet/mobile, scrollable tables)
