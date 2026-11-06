# e07s02 — Prometheus metrics

**type:** feature
**risk:** P1
**context:** e07-observability
**bcps:** 4

## Context

GET /metrics exposes Prometheus text format. Repo health gauges: repos_total, open_issues, stale_issues, open_prs, stale_prs, total_branches, workflow_status, workflow_failures, check_status, last_commit_timestamp, data_fetched_timestamp, oldest_issue_age, oldest_pr_age. Age distribution histograms: issue_age_seconds, pr_age_seconds. Performance: check_run_duration_seconds, action_run_duration_seconds, data_refresh_duration_seconds. GitHub API: api_requests_total, rate_limit_remaining, rate_limit_reset. Metrics documented in METRICS.md.

## Requirements

#### ADDED: Prometheus metrics
GET /metrics exposes Prometheus text format. Repo health gauges: repos_total, open_issues, stale_issues, open_prs, stale_prs, total_branches, workflow_status, workflow_failures, check_status, last_commit_timestamp, data_fetched_timestamp, oldest_issue_age, oldest_pr_age. Age distribution histograms: issue_age_seconds, pr_age_seconds. Performance: check_run_duration_seconds, action_run_duration_seconds, data_refresh_duration_seconds. GitHub API: api_requests_total, rate_limit_remaining, rate_limit_reset. Metrics documented in METRICS.md.

## Acceptance Criteria

```gherkin
Feature: Prometheus metrics
  Scenario: Core functionality works as expected
    Given the environment is initialized
    When Prometheus metrics is executed
    Then all assertions pass and status is done
```

## Steps

1. **Implementation** — Prometheus metrics
   → verify: `curl -s http://localhost:8000/metrics | grep -q 'grimoire_repositories_total'`

## Verification

Run runnable verify commands:
```bash
curl -s http://localhost:8000/metrics | grep -q 'grimoire_repositories_total'
```
