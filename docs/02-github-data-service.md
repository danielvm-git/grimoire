# Module 2: GitHub Data Service

Fetch and cache repository metadata from the GitHub API. Resolve repos from static lists and team memberships. Provide a service layer that the rest of the app queries for repo stats.

**Dependencies:** Module 1 (config, models, database).

## 2.1 — GitHub API Client

**File:** `src/grimoire/github/client.py`

Thin async wrapper around `httpx.AsyncClient` for the GitHub REST API.

### Methods

```python
class GitHubClient:
    def __init__(self, token: str, engine: AsyncEngine): ...

    async def get_team_repos(self, org: str, team_slug: str) -> list[dict]: ...
    async def get_repo(self, full_name: str) -> dict: ...
    async def get_open_issues(self, full_name: str) -> list[dict]: ...
    async def get_open_pull_requests(self, full_name: str) -> list[dict]: ...
    async def get_workflows(self, full_name: str) -> list[dict]: ...
    async def get_workflow_runs(self, full_name: str, branch: str) -> list[dict]: ...
    async def get_default_branch(self, full_name: str) -> str: ...
    async def get_branches(self, full_name: str) -> list[dict]: ...
    async def get_branch(self, full_name: str, branch: str) -> dict: ...
    async def get_check_runs_for_ref(self, full_name: str, ref: str) -> list[dict]: ...
```

### Core implementation

- Accept `token` in constructor, set `Authorization: Bearer {token}` header.
- Use `httpx.AsyncClient` with base URL `https://api.github.com`.
- Handle pagination via GitHub's `Link` header — follow `rel="next"` until exhausted.
- Use `per_page=100` on all list endpoints to minimize pagination.

### API call optimization

The GitHub REST API has a rate limit of 5,000 requests/hour for authenticated users. With 50+ repos being refreshed periodically, minimizing calls is critical.

**Conditional requests (ETags):**
- On every API response, store the `ETag` and `Last-Modified` headers in the `CachedETag` DB table, keyed by the full request URL.
- On subsequent requests, send `If-None-Match` (ETag) and `If-Modified-Since` headers.
- If GitHub returns `304 Not Modified`, skip parsing and use cached data. These 304 responses do **not** count against the rate limit.
- This is the primary optimization: after the first full fetch, most subsequent refreshes are free.

**Efficient fetching per resource type:**
- **Issues:** Use `GET /repos/{owner}/{repo}/issues?state=open&per_page=100`. This returns both issues and PRs mixed together — filter client-side by excluding items that have a `pull_request` key in the JSON. Full list is needed to compute stale counts.
- **Pull requests:** Use `GET /repos/{owner}/{repo}/pulls?state=open&per_page=100` (the Pulls API, not the Issues API). Full list is needed to compute stale counts.
- **Workflows:** Use `GET /repos/{owner}/{repo}/actions/workflows` to list workflows, then `GET /repos/{owner}/{repo}/actions/workflows/{id}/runs?branch={branch}&per_page=1` to get only the latest run per workflow+branch.
- Use `per_page=100` on all list endpoints to minimize pagination.

**Note on GraphQL:** GitHub's GraphQL API could batch queries for multiple repos into a single call. This is deferred as a future optimization — REST with ETags is simpler and provides sufficient efficiency. GraphQL has its own rate limiting (point-based), different error model, and adds implementation complexity.

**Rate limit awareness:**
- After every API response, read `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers.
- Track remaining calls and reset time. Expose both as Prometheus metrics.
- If remaining < 10% of limit: enter **degraded mode** — skip non-essential refreshes, only fetch data the user is actively viewing. Show a warning banner on the dashboard.
- If remaining = 0: pause all GitHub API calls until the reset timestamp. Show a global warning with countdown.

### Failure handling

- Every GitHub API call is wrapped in try/except with specific error types.
- Typed exceptions: `GitHubAPIError`, `RateLimitError`, `NotFoundError`.
- **Transient failures** (5xx, timeout, network error): retry up to 3 times with exponential backoff (1s, 2s, 4s).
- **Persistent failures** (4xx other than 404, repeated 5xx): log the error, keep last-known cached data, mark the affected repo with a warning.
- **404 Not Found**: log as warning, mark repo with "Repository not found" warning. Do not retry.
- **403 Forbidden**: could be rate limit or permissions. Check headers to distinguish. If rate limit, trigger degraded mode. If permissions, log and warn.
- Failures never raise to the caller — always return cached data with warnings populated.

## 2.2 — Repository Resolution Service

**File:** `src/grimoire/github/service.py`

High-level service that resolves the configured repo sources into a list of `TrackedRepository` objects and fetches their stats.

### Functions

```python
async def resolve_repositories(
    config: GrimoireConfig, client: GitHubClient
) -> list[TrackedRepository]:
    """
    For each entry in config.repositories:
      - StaticRepoSource: validate repo exists, resolve default branch if
        no branches specified.
      - TeamRepoSource: fetch team repos, exclude listed repos, filter out
        archived repos.
    Deduplicate by full_name (merge branches if same repo appears in
    multiple sources).
    Always filter out archived repositories.
    """

async def fetch_repository_stats(
    repo: TrackedRepository,
    client: GitHubClient,
    staleness: StalenessConfig,
) -> RepositoryStats:
    """
    For a single tracked repo, fetch:
      - open issues count + stale issues count
        (no comments in staleness.issues_days)
      - open PRs count + stale PRs count
        (no pushes or comments in staleness.pull_requests_days)
      - workflow statuses for each observed branch
      - last commit time across all observed branches
      - total branch count + stale branch count
        (no commits in staleness.branches_days)
    Return a RepositoryStats object. On failure, return stats with
    warnings populated and counts from the last cached values.
    """

async def refresh_all_stats(
    config: GrimoireConfig, client: GitHubClient
) -> list[RepositoryStats]:
    """
    Resolve repos, then fetch stats for all concurrently
    (bounded by asyncio.Semaphore(10)).
    Write results to DB cache. Update in-memory cache.
    """
```

## 2.3 — Caching Strategy (disk + memory)

All fetched data is persisted to the SQLite database as the **persistent cache**:

- On startup, load the latest cached data from the DB immediately — the dashboard is functional right away without any GitHub API calls.
- Keep an in-memory copy (loaded from DB) for fast reads by the web layer. The web layer never calls the GitHub API directly.
- The scheduler refreshes data every `refresh_interval_minutes`: fetches from GitHub API, writes to DB, updates in-memory cache.
- Each cached record stores a `fetched_at` timestamp. The dashboard shows "last updated: X minutes ago" so the user knows data freshness.
- A restart only triggers an API refresh if the cache is older than `refresh_interval_minutes`.

### DB tables for cached data

| Table | Columns |
|---|---|
| `cached_repository` | full_name, default_branch, archived, source, last_commit_at, total_branches, stale_branches, fetched_at |
| `cached_issue` | repo_full_name, title, number, url, created_at, last_comment_at, fetched_at |
| `cached_pull_request` | repo_full_name, title, number, url, author, created_at, last_push_at, last_comment_at, fetched_at |
| `cached_workflow_status` | repo_full_name, workflow_name, branch, status, url, run_url, fetched_at |
| `cached_etag` | endpoint_url, etag, last_modified |

## 2.4 — Repos REST API

**File:** `src/grimoire/github/router.py`

Expose cached repository data and a manual refresh trigger via REST endpoints.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/repos` | List all tracked repos with latest cached stats |
| `GET` | `/api/repos/{owner}/{name}` | Detailed stats for a single repo (issues, PRs, workflows, checks) |
| `POST` | `/api/refresh` | Trigger an immediate data refresh. Returns 202 Accepted; refresh runs in the background |

### Response models

```python
class RepoSummary(BaseModel):
    full_name: str
    default_branch: str
    branches: list[str]
    source: str                     # "static" | "team:org/team-name"
    open_issues: int
    stale_issues: int
    open_pull_requests: int
    stale_pull_requests: int
    workflow_failures: int          # count of failing workflows across all branches
    check_failures: int             # count of failing checks across all branches
    last_commit_at: datetime | None # most recent commit across observed branches
    total_branches: int             # total number of branches in the repo
    stale_branches: int             # branches with no commits in staleness.branches_days
    warnings: list[str]
    fetched_at: datetime

class RepoListResponse(BaseModel):
    repositories: list[RepoSummary]
    last_refresh: datetime | None

class RepoDetailResponse(BaseModel):
    full_name: str
    default_branch: str
    branches: list[str]
    source: str
    open_issues: int
    stale_issues: list[IssueResponse]
    open_pull_requests: int
    stale_pull_requests: list[PullRequestResponse]
    workflows: list[WorkflowStatusResponse]
    checks: list[CheckResultResponse]   # from checks engine
    warnings: list[str]
    fetched_at: datetime

class IssueResponse(BaseModel):
    title: str
    number: int
    url: str
    created_at: datetime
    last_comment_at: datetime | None

class PullRequestResponse(BaseModel):
    title: str
    number: int
    url: str
    author: str
    created_at: datetime
    last_push_at: datetime | None
    last_comment_at: datetime | None

class WorkflowStatusResponse(BaseModel):
    name: str
    branch: str
    status: str
    url: str

class RefreshResponse(BaseModel):
    message: str   # "Refresh started"
```

### Notes

- `GET /api/repos` reads from the in-memory cache — no GitHub API calls, sub-millisecond.
- `GET /api/repos/{owner}/{name}` also reads from cache, enriched with check results from the DB.
- `POST /api/refresh` schedules an immediate background refresh via the scheduler, returns 202 immediately. The web layer detects completion via the cache's `fetched_at` timestamp.

## Acceptance Criteria

- [ ] `GET /api/repos` returns all tracked repos with correct cached stats
- [ ] `GET /api/repos/{owner}/{name}` returns detailed info including stale items, workflows, checks
- [ ] `GET /api/repos/{owner}/{name}` returns 404 for untracked repos
- [ ] `POST /api/refresh` returns 202 and triggers a background refresh
- [ ] `resolve_repositories` correctly handles static repos, team repos, exclusions, and archived filtering
- [ ] `fetch_repository_stats` returns correct issue/PR/workflow counts
- [ ] Stale detection works: issues with no comments beyond threshold, PRs with no pushes/comments beyond threshold
- [ ] Pagination works for repos with >30 issues/PRs
- [ ] Rate limiting is handled gracefully (back off, retry)
- [ ] Conditional requests with ETags reduce API call count (304 responses don't re-fetch)
- [ ] Data is persisted to SQLite and survives application restarts
- [ ] On startup, cached data is loaded from DB without making any API calls
- [ ] Failures are captured as warnings in `RepositoryStats.warnings`, not exceptions
- [ ] Rate limit approaching/exhausted triggers degraded mode with user-visible warning
- [ ] Tests use `respx` to mock GitHub API responses
