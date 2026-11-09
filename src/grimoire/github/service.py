"""Repository resolution and stats fetching service."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.config import (
    GrimoireConfig,
    StalenessConfig,
    StaticRepoSource,
    TeamRepoSource,
    UserRepoSource,
)
from grimoire.database import (
    CachedIssue,
    CachedPullRequest,
    CachedRepository,
    CachedWorkflowStatus,
    CheckResultRecord,
)
from grimoire.db_exec import exec_raw, retry_on_lock
from grimoire.github.client import GitHubClient, NotFoundError
from grimoire.models import (
    IssueDetail,
    PullRequestDetail,
    RepositoryStats,
    TrackedRepository,
    WorkflowStatus,
)
from grimoire.observability.metrics import remove_repo_metrics

logger = logging.getLogger(__name__)

_CONCURRENCY_LIMIT = 10


def _parse_run_time(run: dict[str, Any]) -> datetime | None:
    """Return the run's last-updated time as an aware datetime, if present."""
    return _parse_dt(run.get("updated_at") or run.get("created_at"))


def _brief_error(exc: Exception) -> str:
    """Return a concise, user-friendly description of a fetch error."""
    import httpx

    msg = str(exc)
    if isinstance(exc, httpx.RemoteProtocolError) or "disconnected" in msg.lower():
        return "GitHub disconnected — likely a transient issue. Will retry on next refresh."
    if isinstance(exc, httpx.TimeoutException) or "timeout" in msg.lower():
        return "Request timed out — GitHub may be slow. Will retry on next refresh."
    if "rate limit" in msg.lower():
        return "GitHub API rate limit exceeded. Will resume when the limit resets."
    if isinstance(exc, httpx.ConnectError):
        return "Connection failed — check network connectivity."
    # Generic fallback: truncate long messages
    if len(msg) > 120:
        msg = msg[:117] + "…"
    return msg


# ---------------------------------------------------------------------------
# Refresh progress tracking
# ---------------------------------------------------------------------------


@dataclass
class RefreshProgress:
    """Tracks execution progress of a running data refresh."""

    completed: int = 0
    total: int = 0


_refresh_progress: RefreshProgress | None = None
# Set synchronously before the first await, so two callers cannot both start a
# refresh between the check and the scheduled background task.
_refresh_active = False


class RefreshAlreadyRunning(Exception):
    """Raised when a refresh is requested while one is already in progress."""


def is_refresh_running() -> bool:
    """Return True if a data refresh is currently claimed or in progress."""
    return _refresh_active or _refresh_progress is not None


def get_refresh_progress() -> RefreshProgress | None:
    """Return the progress tracker for a running refresh, or None if idle."""
    return _refresh_progress


def _workflow_matches_filter(
    wf_name: str, include: list[str], exclude: list[str]
) -> bool:
    """Return True if the workflow should be tracked after applying filters.

    * If *include* is non-empty, the name must match at least one include pattern.
    * If *exclude* is non-empty, the name must NOT match any exclude pattern.
    * Both use ``fnmatch`` glob matching (case-sensitive).
    """
    if include and not any(fnmatch(wf_name, pat) for pat in include):
        return False
    if exclude and any(fnmatch(wf_name, pat) for pat in exclude):
        return False
    return True


# ---------------------------------------------------------------------------
# resolve_repositories
# ---------------------------------------------------------------------------


async def resolve_repositories(
    config: GrimoireConfig, client: GitHubClient
) -> list[TrackedRepository]:
    """Build the list of tracked repos from config, validating via the API."""
    seen: dict[str, TrackedRepository] = {}

    # Load cached repository metadata once so that 304 cache hits can recover
    # archived/default_branch from the DB instead of using blind defaults (bug #7).
    cached_repo_meta: dict[str, CachedRepository] = {}
    async with AsyncSession(client._engine) as session:
        for cr in (await session.exec(select(CachedRepository))).all():
            cached_repo_meta[cr.full_name] = cr

    sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

    async def _resolve_source(source: object) -> list[TrackedRepository]:
        async with sem:
            if isinstance(source, StaticRepoSource):
                repo = await _resolve_static(source, client, cached_repo_meta)
                return [repo] if repo is not None else []
            if isinstance(source, TeamRepoSource):
                return await _resolve_team(source, client, cached_repo_meta)
            if isinstance(source, UserRepoSource):
                return await _resolve_user(source, client, cached_repo_meta)
            return []

    # Resolve all sources concurrently; gather preserves config order so the
    # merge below keeps the same precedence as the previous serial loop.
    groups = await asyncio.gather(
        *(_resolve_source(source) for source in config.repositories)
    )
    for group in groups:
        for repo in group:
            existing = seen.get(repo.full_name)
            if existing is None:
                seen[repo.full_name] = repo
            else:
                merged = list(dict.fromkeys(existing.branches + repo.branches))
                seen[repo.full_name] = existing.model_copy(update={"branches": merged})

    return list(seen.values())


async def _remember_archived_repo(
    client: GitHubClient, full_name: str, default_branch: str = "main"
) -> None:
    """Persist an archived observation so a later ETag 304 still skips it.

    A tracked repo that becomes archived is removed from the active set, but
    without a tombstone the cached ``archived`` flag stays False and the next
    304 re-tracks it (bug: archived-cache-roundtrip).
    """
    now = datetime.now(UTC)
    async with AsyncSession(client._engine) as session:
        row = await session.get(CachedRepository, full_name)
        if row is None:
            session.add(
                CachedRepository(
                    full_name=full_name,
                    default_branch=default_branch,
                    archived=True,
                    fetched_at=now,
                )
            )
        else:
            row.archived = True
            if not row.default_branch:
                row.default_branch = default_branch
            row.fetched_at = now
            session.add(row)
        await session.commit()


async def _resolve_static(
    source: StaticRepoSource,
    client: GitHubClient,
    cached_repo_meta: dict[str, CachedRepository] | None = None,
) -> TrackedRepository | None:
    try:
        data = await client.get_repo(source.repo)
        if data is None:
            # 304 cache hit — recover archived/default_branch from the DB cache
            # rather than blindly defaulting (bug #7). Fall back to conservative
            # defaults only when no cached row exists.
            cached = (cached_repo_meta or {}).get(source.repo)
            if cached is not None:
                default_branch = cached.default_branch or "main"
                archived = cached.archived
            else:
                default_branch = "main"
                archived = False
        else:
            default_branch = data.get("default_branch", "main")
            archived = data.get("archived", False)

        if archived:
            await _remember_archived_repo(client, source.repo, default_branch)
            logger.info("Skipping archived repository %s", source.repo)
            return None

        branches = source.branches if source.branches else [default_branch]
        return TrackedRepository(
            full_name=source.repo,
            default_branch=default_branch,
            branches=branches,
            source="static",
            workflow_include=source.workflows.include,
            workflow_exclude=source.workflows.exclude,
        )
    except Exception:
        logger.warning(
            "Failed to resolve static repo %s, keeping cached entry if any",
            source.repo,
            exc_info=True,
        )
        # A transient API error must not drop the repo: prune_stale_data would
        # treat it as untracked and delete its cache, history and clone.
        cached = (cached_repo_meta or {}).get(source.repo)
        if cached is None or cached.archived:
            return None
        return _tracked_from_cache(cached, source.branches)


def _tracked_from_cache(
    cached: CachedRepository, branches: list[str] | None = None
) -> TrackedRepository:
    """Rebuild a tracked repo from its cached row when the API is unavailable."""
    default_branch = cached.default_branch or "main"
    return TrackedRepository(
        full_name=cached.full_name,
        default_branch=default_branch,
        branches=branches
        or json.loads(cached.branches_json or "[]")
        or [default_branch],
        source=cached.source,  # type: ignore[arg-type]
    )


async def _resolve_team(
    source: TeamRepoSource,
    client: GitHubClient,
    cached_repo_meta: dict[str, CachedRepository] | None = None,
) -> list[TrackedRepository]:
    # team format: "org/team-slug"
    try:
        org, team_slug = source.team.split("/", 1)
    except ValueError:
        logger.warning("Invalid team format %r, expected 'org/team-slug'", source.team)
        return []

    try:
        repos = await client.get_team_repos(org, team_slug)
    except Exception:
        logger.warning(
            "Failed to fetch repos for team %s, keeping cached team repos",
            source.team,
            exc_info=True,
        )
        excluded = set(source.exclude)
        return [
            _tracked_from_cache(cached)
            for cached in (cached_repo_meta or {}).values()
            if cached.source == "team"
            and not cached.archived
            and cached.full_name not in excluded
        ]

    exclude_set = set(source.exclude)
    resolved: list[TrackedRepository] = []

    for repo_data in repos:
        full_name = repo_data.get("full_name", "")
        if full_name in exclude_set:
            continue
        default_branch = repo_data.get("default_branch", "main")
        if repo_data.get("archived", False):
            await _remember_archived_repo(client, full_name, default_branch)
            continue

        resolved.append(
            TrackedRepository(
                full_name=full_name,
                default_branch=default_branch,
                branches=[default_branch],
                source=f"team:{source.team}",
                workflow_include=source.workflows.include,
                workflow_exclude=source.workflows.exclude,
            )
        )

    return resolved


async def _resolve_user(
    source: UserRepoSource,
    client: GitHubClient,
    cached_repo_meta: dict[str, CachedRepository] | None = None,
) -> list[TrackedRepository]:
    """Discover every repository owned by ``source.user``.

    Mirrors :func:`_resolve_team`: an exclusion list, an archived-repo tombstone,
    and a cached fallback so a failed (or 304) listing never empties the
    dashboard.
    """
    source_label = f"user:{source.user}"
    exclude_set = set(source.exclude)

    def _from_cache() -> list[TrackedRepository]:
        return [
            _tracked_from_cache(cached)
            for cached in (cached_repo_meta or {}).values()
            if cached.source == source_label
            and not cached.archived
            and cached.full_name not in exclude_set
        ]

    try:
        repos = await client.get_user_repos(source.user)
    except Exception:
        logger.warning(
            "Failed to fetch repos for user %s, keeping cached user repos",
            source.user,
            exc_info=True,
        )
        return _from_cache()

    if repos is None:
        # 304 Not Modified: the account did not change.
        return _from_cache()

    resolved: list[TrackedRepository] = []
    for repo_data in repos:
        full_name = repo_data.get("full_name", "")
        if not full_name or full_name in exclude_set:
            continue
        default_branch = repo_data.get("default_branch", "main")
        if repo_data.get("archived", False):
            await _remember_archived_repo(client, full_name, default_branch)
            continue
        resolved.append(
            TrackedRepository(
                full_name=full_name,
                default_branch=default_branch,
                branches=[default_branch],
                source=source_label,
                workflow_include=source.workflows.include,
                workflow_exclude=source.workflows.exclude,
            )
        )
    return resolved


# ---------------------------------------------------------------------------
# fetch_repository_stats
# ---------------------------------------------------------------------------


async def fetch_repository_stats(
    repo: TrackedRepository,
    client: GitHubClient,
    staleness: StalenessConfig,
    previous: RepositoryStats | None = None,
) -> RepositoryStats:
    """Fetch issues, PRs, and workflow statuses for a single repository.

    When the API returns 304 (Not Modified), *previous* values are preserved
    instead of being reset to zero.
    """
    warnings: list[str] = []
    now = datetime.now(UTC)

    # -- Issues --------------------------------------------------------------
    open_issues = previous.open_issues if previous else 0
    stale_issues = previous.stale_issues if previous else 0
    stale_issue_items: list[IssueDetail] = (
        list(previous.stale_issue_items) if previous else []
    )
    oldest_issue_created_at: datetime | None = (
        previous.oldest_issue_created_at if previous else None
    )
    issue_created_dates: list[datetime] = (
        list(previous.issue_created_dates) if previous else []
    )
    try:
        issues = await client.get_open_issues(repo.full_name)
        if issues is not None:
            open_issues = len(issues)
            stale_issues = 0
            stale_issue_items = []
            issue_created_dates = []
            stale_cutoff = now - timedelta(days=staleness.issues_days)
            for issue in issues:
                created_at = _parse_dt(issue.get("created_at"))
                if created_at is not None:
                    issue_created_dates.append(created_at)
                last_activity = _parse_dt(issue.get("updated_at")) or created_at
                if _is_issue_stale(issue, stale_cutoff):
                    issue_number = issue.get("number")
                    if not issue_number or issue_number <= 0:
                        continue
                    stale_issues += 1
                    stale_issue_items.append(
                        IssueDetail(
                            number=issue_number,
                            title=issue.get("title", ""),
                            url=issue.get("html_url", ""),
                            created_at=created_at or now,
                            last_activity_at=last_activity,
                            author=issue.get("user", {}).get("login", ""),
                        )
                    )
            oldest_issue_created_at = (
                min(issue_created_dates) if issue_created_dates else None
            )
    except Exception as exc:
        warnings.append(
            f"Could not fetch issues for {repo.full_name}: {_brief_error(exc)}"
        )

    # -- Pull Requests -------------------------------------------------------
    open_prs = previous.open_pull_requests if previous else 0
    stale_prs = previous.stale_pull_requests if previous else 0
    stale_pr_items: list[PullRequestDetail] = (
        list(previous.stale_pr_items) if previous else []
    )
    oldest_pr_created_at: datetime | None = (
        previous.oldest_pr_created_at if previous else None
    )
    pr_created_dates: list[datetime] = (
        list(previous.pr_created_dates) if previous else []
    )
    try:
        prs = await client.get_open_pull_requests(repo.full_name)
        if prs is not None:
            open_prs = len(prs)
            stale_prs = 0
            stale_pr_items = []
            pr_created_dates = []
            stale_cutoff = now - timedelta(days=staleness.pull_requests_days)
            for pr in prs:
                created_at = _parse_dt(pr.get("created_at"))
                if created_at is not None:
                    pr_created_dates.append(created_at)
                last_activity = _parse_dt(pr.get("updated_at")) or created_at
                if _is_pr_stale(pr, stale_cutoff):
                    pr_number = pr.get("number")
                    if not pr_number or pr_number <= 0:
                        continue
                    stale_prs += 1
                    stale_pr_items.append(
                        PullRequestDetail(
                            number=pr_number,
                            title=pr.get("title", ""),
                            url=pr.get("html_url", ""),
                            created_at=created_at or now,
                            last_activity_at=last_activity,
                            author=pr.get("user", {}).get("login", ""),
                        )
                    )
            oldest_pr_created_at = min(pr_created_dates) if pr_created_dates else None
    except Exception as exc:
        warnings.append(
            f"Could not fetch PRs for {repo.full_name}: {_brief_error(exc)}"
        )

    # -- Workflows -----------------------------------------------------------
    workflow_statuses: list[WorkflowStatus] = (
        list(previous.workflows) if previous else []
    )
    # Build lookup of previous statuses so we can fall back on 304 cache hits
    prev_wf_map: dict[tuple[str, str], WorkflowStatus] = {}
    if previous:
        for pw in previous.workflows:
            prev_wf_map[(pw.name, pw.branch)] = pw
    try:
        workflows = await client.get_workflows(repo.full_name)
        if workflows is not None:
            workflow_statuses = []  # fresh data, reset
            for branch in repo.branches:
                for wf in workflows:
                    wf_id = wf.get("id")
                    wf_name = wf.get("name", "unknown")
                    if wf_id is None:
                        continue
                    if not _workflow_matches_filter(
                        wf_name, repo.workflow_include, repo.workflow_exclude
                    ):
                        continue
                    try:
                        runs = await client.get_workflow_runs(
                            repo.full_name, wf_id, branch
                        )
                        if runs is not None and runs:
                            run = runs[0]
                            conclusion = run.get("conclusion") or "pending"
                            status_str = _map_conclusion(conclusion)
                            workflow_statuses.append(
                                WorkflowStatus(
                                    name=wf_name,
                                    branch=branch,
                                    status=status_str,
                                    url=wf.get("html_url", ""),
                                    run_url=run.get("html_url", ""),
                                    run_at=_parse_run_time(run),
                                )
                            )
                        elif runs is None:
                            # 304 cache hit — preserve previous status if available
                            prev = prev_wf_map.get((wf_name, branch))
                            if prev is not None:
                                workflow_statuses.append(prev)
                    except NotFoundError:
                        pass  # Non-existing branches from config are silently ignored
                    except Exception as exc:
                        warnings.append(
                            f"Could not fetch runs for workflow '{wf_name}' on {branch}: {_brief_error(exc)}"
                        )
    except Exception as exc:
        warnings.append(
            f"Could not fetch workflows for {repo.full_name}: {_brief_error(exc)}"
        )

    # -- Branches & last commit ----------------------------------------------
    last_commit_at: datetime | None = previous.last_commit_at if previous else None
    total_branches: int = previous.total_branches if previous else 0

    # Fetch last commit time for each observed branch
    branch_commit_dates: list[datetime] = []
    for branch in repo.branches:
        try:
            branch_data = await client.get_branch(repo.full_name, branch)
            if branch_data is not None:
                commit_date_str = (
                    branch_data.get("commit", {})
                    .get("commit", {})
                    .get("committer", {})
                    .get("date")
                )
                dt = _parse_dt(commit_date_str)
                if dt is not None:
                    branch_commit_dates.append(dt)
        except NotFoundError:
            pass  # Non-existing branches from config are silently ignored
        except Exception as exc:
            warnings.append(
                f"Could not fetch branch '{branch}' info: {_brief_error(exc)}"
            )

    if branch_commit_dates:
        last_commit_at = max(branch_commit_dates)

    # Fetch all branches for total count
    try:
        all_branches = await client.get_branches(repo.full_name)
        if all_branches is not None:
            total_branches = len(all_branches)
    except Exception as exc:
        warnings.append(
            f"Could not fetch branches for {repo.full_name}: {_brief_error(exc)}"
        )

    return RepositoryStats(
        full_name=repo.full_name,
        default_branch=repo.default_branch,
        open_issues=open_issues,
        stale_issues=stale_issues,
        open_pull_requests=open_prs,
        stale_pull_requests=stale_prs,
        workflows=workflow_statuses,
        stale_issue_items=stale_issue_items,
        stale_pr_items=stale_pr_items,
        warnings=warnings,
        fetched_at=now,
        last_commit_at=last_commit_at,
        total_branches=total_branches,
        oldest_issue_created_at=oldest_issue_created_at,
        oldest_pr_created_at=oldest_pr_created_at,
        issue_created_dates=issue_created_dates,
        pr_created_dates=pr_created_dates,
    )


def _map_conclusion(conclusion: str) -> str:
    """Map a GitHub run conclusion (or status) onto a dashboard status.

    ``skipped`` and ``neutral`` are real outcomes, not unknowns: a conditional
    deploy that never ran must not look like an unreadable workflow.
    """
    mapping = {
        "success": "success",
        "failure": "failure",
        "cancelled": "failure",
        "timed_out": "failure",
        "startup_failure": "failure",
        "stale": "failure",
        "skipped": "skipped",
        "neutral": "neutral",
        "action_required": "pending",
        "pending": "pending",
        "queued": "pending",
        "in_progress": "pending",
    }
    return mapping.get(conclusion, "unknown")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _is_issue_stale(issue: dict[str, Any], cutoff: datetime) -> bool:
    """An issue is stale if its last comment (or creation) is before *cutoff*."""
    last_comment = _parse_dt(issue.get("updated_at"))
    created = _parse_dt(issue.get("created_at"))
    reference = last_comment or created
    if reference is None:
        return True
    return reference < cutoff


def _is_pr_stale(pr: dict[str, Any], cutoff: datetime) -> bool:
    """A PR is stale if max(last push, last comment) is before *cutoff*."""
    updated = _parse_dt(pr.get("updated_at"))
    created = _parse_dt(pr.get("created_at"))
    reference = updated or created
    if reference is None:
        return True
    return reference < cutoff


# ---------------------------------------------------------------------------
# refresh_all_stats
# ---------------------------------------------------------------------------


async def refresh_all_stats(
    config: GrimoireConfig, client: GitHubClient
) -> tuple[list[TrackedRepository], list[RepositoryStats]]:
    """Resolve repos, fetch stats concurrently, persist to DB, return results."""
    global _refresh_active, _refresh_progress  # noqa: PLW0603

    if _refresh_active:
        raise RefreshAlreadyRunning("A data refresh is already in progress")
    _refresh_active = True

    # Mark refresh as running immediately (before any async work or config
    # inspection) so polling endpoints always see a progress object.
    progress = RefreshProgress()
    _refresh_progress = progress

    try:
        # Compute a preliminary repo count from config so the progress bar can
        # show a meaningful denominator before any async work completes.
        # Static repos are known exactly; team repos need API resolution, so we
        # fall back to the cached count if available.
        progress.total = sum(
            1 for src in config.repositories if isinstance(src, StaticRepoSource)
        )

        # Load previous data so 304 (Not Modified) responses preserve old values
        cached_repos, old_stats_list = await load_stats_from_db(client._engine)
        old_stats_map = {s.full_name: s for s in old_stats_list}

        # Refine the estimate with the cached count (covers team repos).
        if cached_repos and len(cached_repos) > progress.total:
            progress.total = len(cached_repos)

        repos = await resolve_repositories(config, client)

        # When the GitHub API returns 304 for repo resolution (ETag cache hit),
        # resolve_repositories returns an empty list because the paginated response
        # is None.  Fall back to the DB-cached repo list so we don't lose data.
        if not repos and cached_repos:
            logger.info(
                "Repo resolution returned no results (likely 304 cache hit), reusing %d cached repos",
                len(cached_repos),
            )
            repos = cached_repos

        progress.total = len(repos)

        sem = asyncio.Semaphore(_CONCURRENCY_LIMIT)

        async def _fetch(repo: TrackedRepository) -> RepositoryStats:
            async with sem:
                result = await fetch_repository_stats(
                    repo,
                    client,
                    config.staleness,
                    previous=old_stats_map.get(repo.full_name),
                )
                progress.completed += 1
                return result

        stats = await asyncio.gather(*[_fetch(r) for r in repos])
        stats_list = list(stats)

        await save_stats_to_db(
            client._engine,
            stats_list,
            repos,
        )
        return repos, stats_list
    finally:
        _refresh_progress = None
        _refresh_active = False


# ---------------------------------------------------------------------------
# DB persistence helpers
# ---------------------------------------------------------------------------


async def save_stats_to_db(
    engine: AsyncEngine,
    stats_list: list[RepositoryStats],
    repos: list[TrackedRepository],
) -> None:
    """Clear old cached data for each repo and write fresh records.

    A momentary ``database is locked`` must not discard a refresh that already
    paid for every API call, so the whole write transaction is retried.
    """
    await retry_on_lock(lambda: _write_stats_to_db(engine, stats_list, repos))


async def _write_stats_to_db(
    engine: AsyncEngine,
    stats_list: list[RepositoryStats],
    repos: list[TrackedRepository],
) -> None:
    """Persist stats in a single transaction (retried by save_stats_to_db)."""
    now = datetime.now(UTC)
    repo_map = {r.full_name: r for r in repos}

    present_names = [s.full_name for s in stats_list if s.full_name in repo_map]

    async with AsyncSession(engine) as session:
        # Delete old rows for every repo in four statements instead of four
        # statements per repo (was O(4N) sequential round-trips).
        if present_names:
            await exec_raw(
                session,
                delete(CachedIssue).where(
                    CachedIssue.repo_full_name.in_(present_names)  # type: ignore[attr-defined]
                ),
            )
            await exec_raw(
                session,
                delete(CachedPullRequest).where(
                    CachedPullRequest.repo_full_name.in_(present_names)  # type: ignore[attr-defined]
                ),
            )
            await exec_raw(
                session,
                delete(CachedWorkflowStatus).where(
                    CachedWorkflowStatus.repo_full_name.in_(present_names)  # type: ignore[attr-defined]
                ),
            )
            await exec_raw(
                session,
                delete(CachedRepository).where(
                    CachedRepository.full_name.in_(present_names)  # type: ignore[attr-defined]
                ),
            )

        for stats in stats_list:
            repo = repo_map.get(stats.full_name)
            if repo is None:
                continue

            # Write CachedRepository
            session.add(
                CachedRepository(
                    full_name=stats.full_name,
                    default_branch=stats.default_branch,
                    archived=False,
                    source=repo.source,
                    branches_json=json.dumps(repo.branches),
                    open_issues=stats.open_issues,
                    stale_issues=stats.stale_issues,
                    open_pull_requests=stats.open_pull_requests,
                    stale_pull_requests=stats.stale_pull_requests,
                    last_commit_at=stats.last_commit_at,
                    total_branches=stats.total_branches,
                    workflow_include_json=json.dumps(repo.workflow_include),
                    workflow_exclude_json=json.dumps(repo.workflow_exclude),
                    fetched_at=stats.fetched_at or now,
                )
            )

            # Write CachedWorkflowStatus
            for wf in stats.workflows:
                session.add(
                    CachedWorkflowStatus(
                        repo_full_name=stats.full_name,
                        workflow_name=wf.name,
                        branch=wf.branch,
                        status=wf.status,
                        url=wf.url,
                        run_url=wf.run_url,
                        run_at=wf.run_at,
                        fetched_at=stats.fetched_at or now,
                    )
                )

            # Write stale issues
            for item in stats.stale_issue_items:
                session.add(
                    CachedIssue(
                        repo_full_name=stats.full_name,
                        title=item.title,
                        number=item.number,
                        url=item.url,
                        author=item.author,
                        created_at=item.created_at,
                        last_comment_at=item.last_activity_at,
                        fetched_at=stats.fetched_at or now,
                    )
                )

            # Write stale PRs
            for item in stats.stale_pr_items:
                session.add(
                    CachedPullRequest(
                        repo_full_name=stats.full_name,
                        title=item.title,
                        number=item.number,
                        url=item.url,
                        author=item.author,
                        created_at=item.created_at,
                        last_comment_at=item.last_activity_at,
                        fetched_at=stats.fetched_at or now,
                    )
                )

        await session.commit()


async def load_stats_from_db(
    engine: AsyncEngine,
) -> tuple[list[TrackedRepository], list[RepositoryStats]]:
    """Load all cached data from the DB."""
    repos: list[TrackedRepository] = []
    stats_list: list[RepositoryStats] = []

    async with AsyncSession(engine) as session:
        cached_repos = (await session.exec(select(CachedRepository))).all()

        # Bulk-load the child rows once instead of issuing three queries per
        # repo inside the loop below (was O(3N) sequential round-trips).
        wf_by_repo: defaultdict[str, list[CachedWorkflowStatus]] = defaultdict(list)
        for wf_row in (await session.exec(select(CachedWorkflowStatus))).all():
            wf_by_repo[wf_row.repo_full_name].append(wf_row)
        issues_by_repo: defaultdict[str, list[CachedIssue]] = defaultdict(list)
        for issue_row in (await session.exec(select(CachedIssue))).all():
            issues_by_repo[issue_row.repo_full_name].append(issue_row)
        prs_by_repo: defaultdict[str, list[CachedPullRequest]] = defaultdict(list)
        for pr_row in (await session.exec(select(CachedPullRequest))).all():
            prs_by_repo[pr_row.repo_full_name].append(pr_row)

        for cr in cached_repos:
            branches = json.loads(cr.branches_json) if cr.branches_json else []
            repo = TrackedRepository(
                full_name=cr.full_name,
                default_branch=cr.default_branch,
                branches=branches,
                source=cr.source,
                workflow_include=json.loads(cr.workflow_include_json)
                if cr.workflow_include_json
                else [],
                workflow_exclude=json.loads(cr.workflow_exclude_json)
                if cr.workflow_exclude_json
                else [],
            )
            repos.append(repo)

            # Load workflow statuses
            wf_rows = wf_by_repo.get(cr.full_name, [])
            workflows = [
                WorkflowStatus(
                    name=w.workflow_name,
                    branch=w.branch,
                    status=w.status,
                    url=w.url,
                    run_url=w.run_url,
                    run_at=w.run_at,
                )
                for w in wf_rows
            ]

            # Load stale issues from cache
            issue_rows = issues_by_repo.get(cr.full_name, [])
            stale_issue_items = [
                IssueDetail(
                    number=i.number,
                    title=i.title,
                    url=i.url,
                    created_at=i.created_at,
                    last_activity_at=i.last_comment_at,
                    author=i.author,
                )
                for i in issue_rows
            ]

            # Load stale PRs from cache
            pr_rows = prs_by_repo.get(cr.full_name, [])
            stale_pr_items = [
                PullRequestDetail(
                    number=p.number,
                    title=p.title,
                    url=p.url,
                    created_at=p.created_at,
                    last_activity_at=p.last_comment_at,
                    author=p.author,
                )
                for p in pr_rows
            ]

            stats_list.append(
                RepositoryStats(
                    full_name=cr.full_name,
                    default_branch=cr.default_branch,
                    open_issues=cr.open_issues,
                    stale_issues=cr.stale_issues or len(issue_rows),
                    open_pull_requests=cr.open_pull_requests,
                    stale_pull_requests=cr.stale_pull_requests or len(pr_rows),
                    workflows=workflows,
                    stale_issue_items=stale_issue_items,
                    stale_pr_items=stale_pr_items,
                    fetched_at=cr.fetched_at,
                    last_commit_at=cr.last_commit_at,
                    total_branches=cr.total_branches,
                )
            )

    return repos, stats_list


async def prune_removed_repos(engine: AsyncEngine, config: GrimoireConfig) -> int:
    """Delete DB-cached data for repos no longer present in the config.

    Only performs pruning when the config contains exclusively static repo
    sources (``repo:`` entries) so the full set of expected names is known
    without making API calls.  Returns the number of repos pruned.
    """
    has_dynamic_sources = any(
        isinstance(s, (TeamRepoSource, UserRepoSource)) for s in config.repositories
    )
    if has_dynamic_sources:
        logger.debug("Config contains dynamic sources — skipping pre-refresh DB prune")
        return 0

    configured_names: set[str] = set()
    for source in config.repositories:
        if isinstance(source, StaticRepoSource):
            configured_names.add(source.repo)

    if not configured_names:
        return 0

    return len(await _prune_repos_from_db(engine, configured_names))


async def prune_stale_data(
    engine: AsyncEngine,
    repos: list[TrackedRepository],
    workspace_dir: Path | None = None,
) -> int:
    """Remove DB and disk data for repos/workflows no longer in the resolved set.

    Unlike ``prune_removed_repos``, this works after resolution (including
    team sources) because the caller provides the authoritative repo list.
    Also cleans up excluded workflow statuses from the DB and removes
    workspace directories for pruned repos.

    Returns the number of repos pruned.
    """
    active_names = {r.full_name for r in repos}
    pruned_names = await _prune_repos_from_db(engine, active_names)
    pruned = len(pruned_names)
    remove_repo_metrics(pruned_names)

    # Clean up excluded workflows: for each active repo, delete cached
    # workflow statuses that no longer pass the include/exclude filter.
    async with AsyncSession(engine) as session:
        for repo in repos:
            if not repo.workflow_include and not repo.workflow_exclude:
                continue
            wf_rows = (
                await session.exec(
                    select(CachedWorkflowStatus).where(
                        CachedWorkflowStatus.repo_full_name == repo.full_name
                    )
                )
            ).all()
            for wf in wf_rows:
                if not _workflow_matches_filter(
                    wf.workflow_name, repo.workflow_include, repo.workflow_exclude
                ):
                    await session.delete(wf)
        await session.commit()

    # Clean up workspace directories for pruned repos
    if workspace_dir and pruned_names:
        _prune_workspace_dirs(workspace_dir, active_names)

    return pruned


async def _prune_repos_from_db(
    engine: AsyncEngine, active_names: set[str]
) -> list[str]:
    """Delete DB rows for repos not in *active_names*. Returns pruned names."""
    pruned: list[str] = []
    async with AsyncSession(engine) as session:
        cached_rows = (await session.exec(select(CachedRepository))).all()
        stale_names = [
            row.full_name
            for row in cached_rows
            if row.full_name not in active_names and not row.archived
        ]

        for fn in stale_names:
            await exec_raw(
                session,
                delete(CachedIssue).where(CachedIssue.repo_full_name == fn),  # type: ignore[arg-type]
            )
            await exec_raw(
                session,
                delete(CachedPullRequest).where(CachedPullRequest.repo_full_name == fn),  # type: ignore[arg-type]
            )
            await exec_raw(
                session,
                delete(CachedWorkflowStatus).where(
                    CachedWorkflowStatus.repo_full_name == fn  # type: ignore[arg-type]
                ),
            )
            await exec_raw(
                session,
                delete(CheckResultRecord).where(CheckResultRecord.repo_full_name == fn),  # type: ignore[arg-type]
            )
            await exec_raw(
                session,
                delete(CachedRepository).where(CachedRepository.full_name == fn),  # type: ignore[arg-type]
            )
            pruned.append(fn)

        if pruned:
            await session.commit()
            logger.info("Pruned %d repos no longer tracked: %s", len(pruned), pruned)

    return pruned


def _prune_workspace_dirs(workspace_dir: Path, active_names: set[str]) -> None:
    """Remove workspace directories for repos no longer tracked."""
    import shutil

    active_owners: dict[str, set[str]] = {}
    for name in active_names:
        owner, repo = name.split("/", 1)
        active_owners.setdefault(owner, set()).add(repo)

    if not workspace_dir.is_dir():
        return

    for owner_dir in workspace_dir.iterdir():
        if not owner_dir.is_dir() or owner_dir.name.startswith("."):
            continue
        for repo_dir in owner_dir.iterdir():
            if not repo_dir.is_dir() or repo_dir.name.startswith("."):
                continue
            full_name = f"{owner_dir.name}/{repo_dir.name}"
            if full_name not in active_names:
                logger.info("Removing workspace for pruned repo: %s", full_name)
                shutil.rmtree(repo_dir, ignore_errors=True)
        # Remove empty owner directories
        if owner_dir.is_dir() and not any(owner_dir.iterdir()):
            owner_dir.rmdir()
