# Grimoire Metrics Reference

All Prometheus metrics exposed at `GET /metrics`. Scraped using standard Prometheus configuration.

## Repository Health

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `grimoire_repositories_total` | Gauge | — | Number of tracked repositories |
| `grimoire_open_issues_total` | Gauge | `repo` | Open issue count |
| `grimoire_stale_issues_total` | Gauge | `repo` | Stale issue count (exceeds configured staleness threshold) |
| `grimoire_open_pull_requests_total` | Gauge | `repo` | Open pull request count |
| `grimoire_stale_pull_requests_total` | Gauge | `repo` | Stale pull request count (exceeds configured staleness threshold) |
| `grimoire_total_branches` | Gauge | `repo` | Total branch count |
| `grimoire_workflow_status` | Gauge | `repo`, `workflow`, `branch` | Workflow status: 1 = success, 0 = failure |
| `grimoire_workflow_failures_total` | Gauge | `repo` | Number of failing workflows |
| `grimoire_check_status` | Gauge | `repo`, `check`, `branch` | Check status: 1 = pass, 0 = fail |
| `grimoire_last_commit_timestamp_seconds` | Gauge | `repo` | Unix timestamp of the most recent commit |
| `grimoire_data_fetched_timestamp_seconds` | Gauge | `repo` | Unix timestamp of the last data fetch |

## Performance

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `grimoire_check_run_duration_seconds` | Histogram | `check` | Check execution time |
| `grimoire_action_run_duration_seconds` | Histogram | `action` | Action execution time |
| `grimoire_data_refresh_duration_seconds` | Histogram | — | Full data refresh cycle time |

## GitHub API

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `grimoire_github_api_requests_total` | Counter | `endpoint`, `status` | Total API calls made |
| `grimoire_github_api_rate_limit_remaining` | Gauge | — | Current remaining rate limit |
| `grimoire_github_api_rate_limit_reset` | Gauge | — | Unix timestamp of next rate limit reset |
