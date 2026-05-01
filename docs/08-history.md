# Module 8: History

Time-series historical data for trend visualisation. Records daily snapshots of per-repo metrics and serves them via a REST API and Chart.js-powered web page.

**Dependencies:** Module 1 (config, database), Module 2 (GitHub data service), Module 6 (web application).

## 8.1 — Configuration

New `history` section in `config.yaml`:

```yaml
history:
  retention_days: 90  # default: 90 — delete snapshots older than this many days
```

**Pydantic model:** `HistoryConfig(retention_days: int = 90)`

Added to `GrimoireConfig` as `history: HistoryConfig = Field(default_factory=HistoryConfig)`.

## 8.2 — StatsSnapshot Table

**File:** `src/grimoire/database.py`

| Column | Type | Notes |
|--------|------|-------|
| `id` | int | PK, auto |
| `snapshot_date` | date | Calendar date (indexed); part of UNIQUE constraint |
| `timestamp` | datetime | When this snapshot was last written |
| `repo_full_name` | str | Indexed; part of UNIQUE constraint |
| `open_issues` | int | Total open issues |
| `open_prs` | int | Total open PRs |
| `workflow_total` | int | Number of tracked workflows |
| `workflow_failures` | int | Workflows with status "failure" |
| `total_branches` | int | Total branch count |
| `stale_branches` | int | Branches past staleness threshold (snapshot-time config) |
| `issues_by_age_json` | str | JSON `{"7": n, "14": n, ...}` — issues older than N days |
| `prs_by_age_json` | str | Same format for PRs |
| `branches_by_age_json` | str | Same format for branches |

**Unique constraint:** `(repo_full_name, snapshot_date)` — enforced at DB level, upserted via `ON CONFLICT DO UPDATE`.

## 8.3 — Age Buckets for Retroactive Staleness

Fixed thresholds: `[7, 14, 30, 60, 90, 180, 365]` days.

For each snapshot, the number of issues/PRs/branches with age ≥ each threshold is computed and stored as JSON. "Age" uses the same reference as existing staleness logic:

- **Issues/PRs:** `updated_at` (fallback `created_at`)
- **Branches:** last commit committer date

At query time, the API reads the current `StalenessConfig` (e.g. `issues_days=365`), picks the nearest available bucket, and uses that count as the stale series. This allows retroactive recomputation when thresholds change — the charts update instantly.

**Computed in:** `fetch_repository_stats()` in `service.py`, from raw API data. Preserved from `previous` on 304 cache hits.

## 8.4 — Snapshot Recording

**Hook point:** `save_stats_to_db()` in `src/grimoire/github/service.py`.

On each refresh cycle:

1. **Retention cleanup:** Delete snapshots where `snapshot_date < today - retention_days`.
2. **Upsert snapshots:** For each repo, upsert a `StatsSnapshot` row for today's date. The last refresh of the day wins.

Uses SQLite's `INSERT ... ON CONFLICT DO UPDATE` for atomic upsert.

## 8.5 — History REST API

**File:** `src/grimoire/history/router.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/history/global` | Aggregated time-series (SUM across all or selected repos per day) |
| `GET` | `/api/history/{repo}` | Time-series for a single repo |

**Query parameters:**

- `days` (int, default 30, range 1–365): How many days of history to return.
- `repos` (list[str], optional, global endpoint only): Filter to specific repos. Repeated query param: `?repos=a/b&repos=c/d`. When omitted, aggregates all repos.

**Response format:**

```json
{
  "timestamps": ["2025-01-01", "2025-01-02", ...],
  "series": {
    "open_issues": [100, 102, ...],
    "stale_issues": [5, 6, ...],
    "open_prs": [20, 18, ...],
    "stale_prs": [3, 2, ...],
    "workflow_total": [50, 50, ...],
    "workflow_failures": [2, 1, ...],
    "total_branches": [80, 82, ...],
    "stale_branches": [5, 4, ...]
  }
}
```

**Global aggregation:** Groups by `snapshot_date`, sums numeric fields, merges age bucket JSON dicts. Filtered by `repos` when provided.

## 8.6 — History Web Page

**Route:** `GET /history` (in `src/grimoire/web/router.py`)
**Template:** `src/grimoire/web/templates/history.html`

Layout:
- **Controls bar:** Time range buttons (7d, 30d default, 90d) + Tom Select multi-select repo dropdown (searchable, tag-based) + Reset button
- **Issues & Pull Requests section:** Issues chart + PRs chart (side by side)
- **Workflows & Branches section:** Workflows chart + Branches chart (side by side)

**Behavior:**
- No repos selected → fetches `/api/history/global?days=N` (all repos aggregated)
- Repos selected → fetches `/api/history/global?days=N&repos=...` (filtered aggregate)
- Time range or repo selection changes → re-fetch and re-render all 4 charts
- Reset button → clears Tom Select, refetches global
- Empty results → destroys charts, shows "no data" message
- AbortController used to prevent race conditions from overlapping requests

**Chart library:** Chart.js 4.x (CDN). Line charts with dual series (e.g. Open + Stale).
**Dropdown library:** Tom Select 2.x (CDN). Styled to match DaisyUI theme.

**Navigation:** "History" link added to navbar in `base.html` (between "Actions" and theme toggle).

## 8.7 — Data Volume

With daily snapshots (one row per repo per day):

| Retention | Rows (70 repos) | Approx. size |
|-----------|-----------------|-------------|
| 30 days | 2,100 | ~0.8 MB |
| 90 days | 6,300 | ~2.3 MB |
| 365 days | 25,550 | ~9.5 MB |

## What This Does NOT Include

- Check metrics (check results have a different lifecycle; deferred to a future version)
- Per-branch history
- Snapshot downsampling (daily is already compact)

## Acceptance Criteria

- [ ] `StatsSnapshot` table created on startup; UNIQUE constraint on `(repo_full_name, snapshot_date)`
- [ ] Each refresh cycle upserts one snapshot per repo for today
- [ ] Old snapshots are deleted per `retention_days` config
- [ ] `GET /api/history/global?days=30` returns aggregated series
- [ ] `GET /api/history/global?days=30&repos=a/b&repos=c/d` returns filtered aggregate
- [ ] `GET /api/history/{repo}?days=30` returns per-repo series
- [ ] Stale series uses current `StalenessConfig` to pick age bucket
- [ ] `/history` page has Tom Select multi-select dropdown with type-to-filter search
- [ ] No repos selected = global aggregate; selected repos = filtered aggregate
- [ ] Reset button clears selection and refetches global
- [ ] Two chart sections: Issues & PRs, Workflows & Branches
- [ ] Time range selector (7d/30d/90d) reloads charts
- [ ] AbortController prevents stale responses from overwriting current data
- [ ] Tests cover: snapshot recording, upsert dedup, retention, API endpoints, repos filter, age bucket computation
