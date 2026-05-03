"""Repository resolution and stats fetching service."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.config import GrimoireConfig, StalenessConfig, StaticRepoSource, TeamRepoSource
from grimoire.database import (
    CachedIssue,
    CachedPullRequest,
    CachedRepository,
    CachedWorkflowStatus,
    CheckResultRecord,
    StatsSnapshot,
)
from grimoire.github.client import GitHubClient, NotFoundError
from grimoire.models import (
    IssueDetail,
    PullRequestDetail,
    RepositoryStats,
    TrackedRepository,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)

_CONCURRENCY_LIMIT = 10

AGE_BUCKET_THRESHOLDS = [7, 14, 30, 60, 90, 180, 365]


# ---------------------------------------------------------------------------
# Refresh progress tracking
# ---------------------------------------------------------------------------


@dataclass
class RefreshProgress:
    """Tracks execution progress of a running data refresh."""

    completed: int = 0
    total: int = 0


_refresh_progress: RefreshProgress | None = None


def is_refresh_running() -> bool:
    """Return True if a data refresh is currently in progress."""
    return _refresh_progress is not None


def get_refresh_progress() -> RefreshProgress | None:
    """Return the progress tracker for a running refresh, or None if idle."""
    return _refresh_progress


def _workflow_matches_filter(wf_name: str, include: list[str], exclude: list[str]) -> bool:
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


def _compute_age_buckets(
    activity_dates: list[datetime | None],
    now: datetime,
) -> dict[int, int]:
    """Compute how many items have age >= each threshold in AGE_BUCKET_THRESHOLDS.

    ``activity_dates`` should be the last-activity datetime for each item.
    Returns e.g. ``{7: 12, 14: 10, 30: 8, 60: 5, 90: 3, 180: 1, 365: 0}``.
    """
    ages_days: list[float] = []
    for dt in activity_dates:
        if dt is None:
            ages_days.append(float("inf"))
        else:
            ages_days.append((now - dt).total_seconds() / 86400)
    return {t: sum(1 for a in ages_days if a >= t) for t in AGE_BUCKET_THRESHOLDS}


# ---------------------------------------------------------------------------
# resolve_repositories
# ---------------------------------------------------------------------------


async def resolve_repositories(
    config: GrimoireConfig, client: GitHubClient
) -> list[TrackedRepository]:
    """Build the list of tracked repos from config, validating via the API."""
    seen: dict[str, TrackedRepository] = {}

    for source in config.repositories:
        if isinstance(source, StaticRepoSource):
            await _resolve_static(source, client, seen)
        elif isinstance(source, TeamRepoSource):
            await _resolve_team(source, client, seen)

    return list(seen.values())


async def _resolve_static(
    source: StaticRepoSource,
    client: GitHubClient,
    seen: dict[str, TrackedRepository],
) -> None:
    try:
        data = await client.get_repo(source.repo)
        if data is None:
            # 304 cache hit — use the repo name as-is
            default_branch = "main"
            archived = False
        else:
            default_branch = data.get("default_branch", "main")
            archived = data.get("archived", False)

        if archived:
            logger.info("Skipping archived repository %s", source.repo)
            return

        branches = source.branches if source.branches else [default_branch]

        if source.repo in seen:
            existing = seen[source.repo]
            merged = list(dict.fromkeys(existing.branches + branches))
            seen[source.repo] = existing.model_copy(update={"branches": merged})
        else:
            seen[source.repo] = TrackedRepository(
                full_name=source.repo,
                default_branch=default_branch,
                branches=branches,
                source="static",
                workflow_include=source.workflows.include,
                workflow_exclude=source.workflows.exclude,
            )
    except Exception:
        logger.warning("Failed to resolve static repo %s, skipping", source.repo, exc_info=True)


async def _resolve_team(
    source: TeamRepoSource,
    client: GitHubClient,
    seen: dict[str, TrackedRepository],
) -> None:
    # team format: "org/team-slug"
    try:
        org, team_slug = source.team.split("/", 1)
    except ValueError:
        logger.warning("Invalid team format %r, expected 'org/team-slug'", source.team)
        return

    try:
        repos = await client.get_team_repos(org, team_slug)
    except Exception:
        logger.warning("Failed to fetch repos for team %s, skipping", source.team, exc_info=True)
        return

    exclude_set = set(source.exclude)

    for repo_data in repos:
        full_name = repo_data.get("full_name", "")
        if full_name in exclude_set:
            continue
        if repo_data.get("archived", False):
            continue

        default_branch = repo_data.get("default_branch", "main")
        branches = [default_branch]
        source_label = f"team:{source.team}"

        if full_name in seen:
            existing = seen[full_name]
            merged = list(dict.fromkeys(existing.branches + branches))
            seen[full_name] = existing.model_copy(update={"branches": merged})
        else:
            seen[full_name] = TrackedRepository(
                full_name=full_name,
                default_branch=default_branch,
                branches=branches,
                source=source_label,
                workflow_include=source.workflows.include,
                workflow_exclude=source.workflows.exclude,
            )


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
    stale_issue_items: list[IssueDetail] = list(previous.stale_issue_items) if previous else []
    issues_by_age: dict[int, int] = dict(previous.issues_by_age) if previous else {}
    try:
        issues = await client.get_open_issues(repo.full_name)
        if issues is not None:
            open_issues = len(issues)
            stale_issues = 0
            stale_issue_items = []
            stale_cutoff = now - timedelta(days=staleness.issues_days)
            issue_activity_dates: list[datetime | None] = []
            for issue in issues:
                last_activity = _parse_dt(issue.get("updated_at")) or _parse_dt(
                    issue.get("created_at")
                )
                issue_activity_dates.append(last_activity)
                if _is_issue_stale(issue, stale_cutoff):
                    stale_issues += 1
                    stale_issue_items.append(
                        IssueDetail(
                            number=issue.get("number", 0),
                            title=issue.get("title", ""),
                            url=issue.get("html_url", ""),
                            created_at=_parse_dt(issue.get("created_at")) or now,
                            last_activity_at=last_activity,
                            author=issue.get("user", {}).get("login", ""),
                        )
                    )
            issues_by_age = _compute_age_buckets(issue_activity_dates, now)
    except Exception as exc:
        warnings.append(f"Failed to fetch issues: {exc}")

    # -- Pull Requests -------------------------------------------------------
    open_prs = previous.open_pull_requests if previous else 0
    stale_prs = previous.stale_pull_requests if previous else 0
    stale_pr_items: list[PullRequestDetail] = list(previous.stale_pr_items) if previous else []
    prs_by_age: dict[int, int] = dict(previous.prs_by_age) if previous else {}
    try:
        prs = await client.get_open_pull_requests(repo.full_name)
        if prs is not None:
            open_prs = len(prs)
            stale_prs = 0
            stale_pr_items = []
            stale_cutoff = now - timedelta(days=staleness.pull_requests_days)
            pr_activity_dates: list[datetime | None] = []
            for pr in prs:
                last_activity = _parse_dt(pr.get("updated_at")) or _parse_dt(pr.get("created_at"))
                pr_activity_dates.append(last_activity)
                if _is_pr_stale(pr, stale_cutoff):
                    stale_prs += 1
                    stale_pr_items.append(
                        PullRequestDetail(
                            number=pr.get("number", 0),
                            title=pr.get("title", ""),
                            url=pr.get("html_url", ""),
                            created_at=_parse_dt(pr.get("created_at")) or now,
                            last_activity_at=last_activity,
                            author=pr.get("user", {}).get("login", ""),
                        )
                    )
            prs_by_age = _compute_age_buckets(pr_activity_dates, now)
    except Exception as exc:
        warnings.append(f"Failed to fetch pull requests: {exc}")

    # -- Workflows -----------------------------------------------------------
    workflow_statuses: list[WorkflowStatus] = list(previous.workflows) if previous else []
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
                        runs = await client.get_workflow_runs(repo.full_name, wf_id, branch)
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
                            f"Failed to fetch runs for workflow {wf_name} on {branch}: {exc}"
                        )
    except Exception as exc:
        warnings.append(f"Failed to fetch workflows: {exc}")

    # -- Branches & last commit ----------------------------------------------
    last_commit_at: datetime | None = previous.last_commit_at if previous else None
    total_branches: int = previous.total_branches if previous else 0
    stale_branches: int = previous.stale_branches if previous else 0
    branches_by_age: dict[int, int] = dict(previous.branches_by_age) if previous else {}

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
            warnings.append(f"Failed to fetch branch {branch} info: {exc}")

    if branch_commit_dates:
        last_commit_at = max(branch_commit_dates)

    # Fetch all branches for total/stale counts
    try:
        all_branches = await client.get_branches(repo.full_name)
        if all_branches is not None:
            total_branches = len(all_branches)
            stale_cutoff = now - timedelta(days=staleness.branches_days)
            stale_branches = 0
            all_branch_dates: list[datetime | None] = []
            for b in all_branches:
                commit_date_str = (
                    b.get("commit", {}).get("commit", {}).get("committer", {}).get("date")
                )
                # Branches list returns shallow commit; date may be at top level
                if not commit_date_str:
                    commit_date_str = b.get("commit", {}).get("committer", {}).get("date")
                dt = _parse_dt(commit_date_str)
                all_branch_dates.append(dt)
                if dt is not None and dt < stale_cutoff:
                    stale_branches += 1
            branches_by_age = _compute_age_buckets(all_branch_dates, now)
    except Exception as exc:
        warnings.append(f"Failed to fetch branches: {exc}")

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
        stale_branches=stale_branches,
        issues_by_age=issues_by_age,
        prs_by_age=prs_by_age,
        branches_by_age=branches_by_age,
    )


def _map_conclusion(conclusion: str) -> str:
    mapping = {
        "success": "success",
        "failure": "failure",
        "cancelled": "failure",
        "timed_out": "failure",
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
    global _refresh_progress  # noqa: PLW0603

    # Compute a preliminary repo count from config so the progress bar can
    # show a meaningful denominator before any async work completes.
    # Static repos are known exactly; team repos need API resolution, so we
    # fall back to the cached count if available.
    preliminary_total = sum(1 for src in config.repositories if isinstance(src, StaticRepoSource))

    # Mark refresh as running immediately (before async work begins) so that
    # polling endpoints see it as in-progress right away.
    progress = RefreshProgress(completed=0, total=preliminary_total)
    _refresh_progress = progress

    try:
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
            retention_days=config.history.retention_days,
        )
        return repos, stats_list
    finally:
        _refresh_progress = None


# ---------------------------------------------------------------------------
# DB persistence helpers
# ---------------------------------------------------------------------------


async def save_stats_to_db(
    engine: AsyncEngine,
    stats_list: list[RepositoryStats],
    repos: list[TrackedRepository],
    *,
    retention_days: int = 90,
) -> None:
    """Clear old cached data for each repo and write fresh records.

    Also upserts daily history snapshots and prunes expired ones.
    """
    now = datetime.now(UTC)
    today = now.date()
    repo_map = {r.full_name: r for r in repos}

    async with AsyncSession(engine) as session:
        # -- Retention: prune expired snapshots --------------------------------
        cutoff = today - timedelta(days=retention_days)
        await session.exec(  # type: ignore[call-overload]
            delete(StatsSnapshot).where(StatsSnapshot.snapshot_date < cutoff)  # type: ignore[arg-type]
        )

        for stats in stats_list:
            repo = repo_map.get(stats.full_name)
            if repo is None:
                continue

            # Delete old cached data for this repo
            fn = stats.full_name
            await session.exec(  # type: ignore[call-overload]
                delete(CachedIssue).where(CachedIssue.repo_full_name == fn)  # type: ignore[arg-type]
            )
            await session.exec(  # type: ignore[call-overload]
                delete(CachedPullRequest).where(
                    CachedPullRequest.repo_full_name == fn  # type: ignore[arg-type]
                )
            )
            await session.exec(  # type: ignore[call-overload]
                delete(CachedWorkflowStatus).where(
                    CachedWorkflowStatus.repo_full_name == fn  # type: ignore[arg-type]
                )
            )
            await session.exec(  # type: ignore[call-overload]
                delete(CachedRepository).where(
                    CachedRepository.full_name == fn  # type: ignore[arg-type]
                )
            )

            # Write CachedRepository
            session.add(
                CachedRepository(
                    full_name=stats.full_name,
                    default_branch=stats.default_branch,
                    source=repo.source,
                    branches_json=json.dumps(repo.branches),
                    open_issues=stats.open_issues,
                    stale_issues=stats.stale_issues,
                    open_pull_requests=stats.open_pull_requests,
                    stale_pull_requests=stats.stale_pull_requests,
                    last_commit_at=stats.last_commit_at,
                    total_branches=stats.total_branches,
                    stale_branches=stats.stale_branches,
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

            # -- Upsert daily history snapshot ---------------------------------
            wf_total = len(stats.workflows)
            wf_failures = sum(1 for w in stats.workflows if w.status == "failure")

            await _upsert_snapshot(
                session,
                snapshot_date=today,
                timestamp=now,
                repo_full_name=fn,
                open_issues=stats.open_issues,
                stale_issues=stats.stale_issues,
                open_prs=stats.open_pull_requests,
                stale_prs=stats.stale_pull_requests,
                workflow_total=wf_total,
                workflow_failures=wf_failures,
                total_branches=stats.total_branches,
                stale_branches=stats.stale_branches,
                issues_by_age_json=json.dumps(stats.issues_by_age),
                prs_by_age_json=json.dumps(stats.prs_by_age),
                branches_by_age_json=json.dumps(stats.branches_by_age),
            )

        await session.commit()


async def _upsert_snapshot(
    session: AsyncSession,
    *,
    snapshot_date: date,
    timestamp: datetime,
    repo_full_name: str,
    open_issues: int,
    stale_issues: int,
    open_prs: int,
    stale_prs: int,
    workflow_total: int,
    workflow_failures: int,
    total_branches: int,
    stale_branches: int,
    issues_by_age_json: str,
    prs_by_age_json: str,
    branches_by_age_json: str,
) -> None:
    """Insert or update a daily snapshot for a single repo."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    values = {
        "snapshot_date": snapshot_date,
        "timestamp": timestamp,
        "repo_full_name": repo_full_name,
        "open_issues": open_issues,
        "stale_issues": stale_issues,
        "open_prs": open_prs,
        "stale_prs": stale_prs,
        "workflow_total": workflow_total,
        "workflow_failures": workflow_failures,
        "total_branches": total_branches,
        "stale_branches": stale_branches,
        "issues_by_age_json": issues_by_age_json,
        "prs_by_age_json": prs_by_age_json,
        "branches_by_age_json": branches_by_age_json,
    }
    update_values = {
        k: v for k, v in values.items() if k not in ("snapshot_date", "repo_full_name")
    }

    stmt = sqlite_insert(StatsSnapshot).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["repo_full_name", "snapshot_date"],
        set_=update_values,
    )
    await session.execute(stmt)


async def update_snapshot_checks(
    engine: AsyncEngine,
    check_counts: dict[str, tuple[int, int, int]],
) -> None:
    """Update today's snapshots with check totals after checks complete.

    Args:
        engine: Database engine.
        check_counts: Mapping of repo_full_name → (total, failures, warnings).
    """
    today = date.today()
    async with AsyncSession(engine) as session:
        for repo_name, (total, failures, warnings) in check_counts.items():
            stmt = (
                select(StatsSnapshot)
                .where(StatsSnapshot.repo_full_name == repo_name)
                .where(col(StatsSnapshot.snapshot_date) == today)
            )
            snap = (await session.exec(stmt)).first()
            if snap:
                snap.check_total = total
                snap.check_failures = failures
                snap.check_warnings = warnings
                session.add(snap)
        await session.commit()


async def compute_check_counts(
    engine: AsyncEngine,
    checks: list | None = None,
) -> dict[str, tuple[int, int, int]]:
    """Compute per-repo check totals from latest check results in the DB.

    Args:
        engine: Database engine.
        checks: Optional list of CheckDefinition objects for severity lookup.
            If not provided, all failures count as errors.

    Returns mapping of repo_full_name → (total, failures, warnings).
    """
    from sqlalchemy import text

    # Build severity lookup: slug → severity
    severity_map: dict[str, str] = {}
    if checks:
        for c in checks:
            severity_map[c.slug] = c.severity

    query = text(
        "SELECT cr.check_slug, cr.repo_full_name, cr.passed "
        "FROM check_result cr "
        "INNER JOIN ("
        "  SELECT check_slug, repo_full_name, branch, MAX(timestamp) AS max_ts "
        "  FROM check_result "
        "  GROUP BY check_slug, repo_full_name, branch"
        ") latest ON cr.check_slug = latest.check_slug "
        "AND cr.repo_full_name = latest.repo_full_name "
        "AND cr.branch = latest.branch "
        "AND cr.timestamp = latest.max_ts"
    )
    counts: dict[str, tuple[int, int, int]] = {}
    async with AsyncSession(engine) as session:
        result = await session.execute(query)
        for row in result.all():
            slug = row[0]
            repo_name = row[1]
            passed = bool(row[2])
            total, failures, warnings = counts.get(repo_name, (0, 0, 0))
            total += 1
            if not passed:
                severity = severity_map.get(slug, "error")
                if severity == "warning":
                    warnings += 1
                else:
                    failures += 1
            counts[repo_name] = (total, failures, warnings)
    return counts


async def load_stats_from_db(
    engine: AsyncEngine,
) -> tuple[list[TrackedRepository], list[RepositoryStats]]:
    """Load all cached data from the DB."""
    repos: list[TrackedRepository] = []
    stats_list: list[RepositoryStats] = []

    async with AsyncSession(engine) as session:
        cached_repos = (await session.exec(select(CachedRepository))).all()

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
            wf_rows = (
                await session.exec(
                    select(CachedWorkflowStatus).where(
                        CachedWorkflowStatus.repo_full_name == cr.full_name
                    )
                )
            ).all()
            workflows = [
                WorkflowStatus(
                    name=w.workflow_name,
                    branch=w.branch,
                    status=w.status,
                    url=w.url,
                    run_url=w.run_url,
                )
                for w in wf_rows
            ]

            # Load stale issues from cache
            issue_rows = (
                await session.exec(
                    select(CachedIssue).where(CachedIssue.repo_full_name == cr.full_name)
                )
            ).all()
            stale_issue_items = [
                IssueDetail(
                    number=i.number,
                    title=i.title,
                    url=i.url,
                    created_at=i.created_at,
                    last_activity_at=i.last_comment_at,
                )
                for i in issue_rows
            ]

            # Load stale PRs from cache
            pr_rows = (
                await session.exec(
                    select(CachedPullRequest).where(
                        CachedPullRequest.repo_full_name == cr.full_name
                    )
                )
            ).all()
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
                    stale_branches=cr.stale_branches,
                )
            )

    return repos, stats_list


async def prune_removed_repos(engine: AsyncEngine, config: GrimoireConfig) -> int:
    """Delete DB-cached data for repos no longer present in the config.

    Only performs pruning when the config contains exclusively static repo
    sources (``repo:`` entries) so the full set of expected names is known
    without making API calls.  Returns the number of repos pruned.
    """
    has_team_sources = any(isinstance(s, TeamRepoSource) for s in config.repositories)
    if has_team_sources:
        logger.debug("Config contains team sources — skipping DB prune")
        return 0

    configured_names: set[str] = set()
    for source in config.repositories:
        if isinstance(source, StaticRepoSource):
            configured_names.add(source.repo)

    if not configured_names:
        return 0

    return await _prune_repos_from_db(engine, configured_names)


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
    pruned = await _prune_repos_from_db(engine, active_names)

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
    if workspace_dir and pruned:
        _prune_workspace_dirs(workspace_dir, active_names)

    return pruned


async def _prune_repos_from_db(engine: AsyncEngine, active_names: set[str]) -> int:
    """Delete DB rows for repos not in *active_names*.  Returns count pruned."""
    pruned = 0
    async with AsyncSession(engine) as session:
        cached = (await session.exec(select(CachedRepository.full_name))).all()
        stale_names = [name for name in cached if name not in active_names]

        for fn in stale_names:
            await session.exec(  # type: ignore[call-overload]
                delete(CachedIssue).where(CachedIssue.repo_full_name == fn)  # type: ignore[arg-type]
            )
            await session.exec(  # type: ignore[call-overload]
                delete(CachedPullRequest).where(CachedPullRequest.repo_full_name == fn)  # type: ignore[arg-type]
            )
            await session.exec(  # type: ignore[call-overload]
                delete(CachedWorkflowStatus).where(CachedWorkflowStatus.repo_full_name == fn)  # type: ignore[arg-type]
            )
            await session.exec(  # type: ignore[call-overload]
                delete(CheckResultRecord).where(CheckResultRecord.repo_full_name == fn)  # type: ignore[arg-type]
            )
            await session.exec(  # type: ignore[call-overload]
                delete(CachedRepository).where(CachedRepository.full_name == fn)  # type: ignore[arg-type]
            )
            pruned += 1

        if pruned:
            await session.commit()
            logger.info("Pruned %d repos no longer tracked: %s", pruned, stale_names)

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
