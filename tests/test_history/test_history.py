"""Tests for the history module — snapshot recording, API, and helpers."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.config import StalenessConfig
from grimoire.database import StatsSnapshot, create_tables, get_engine
from grimoire.github.service import (
    AGE_BUCKET_THRESHOLDS,
    _compute_age_buckets,
    save_stats_to_db,
)
from grimoire.history.router import (
    _build_series,
    _extract_stale_series,
    _pick_bucket,
    set_history_state,
)
from grimoire.models import RepositoryStats, TrackedRepository, WorkflowStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine(tmp_path) -> AsyncEngine:
    db_path = str(tmp_path / "test.db")
    eng = await get_engine(db_path)
    await create_tables(eng)
    return eng


def _repo(name: str = "owner/repo1") -> TrackedRepository:
    return TrackedRepository(full_name=name, default_branch="main", branches=["main"])


def _stats(
    name: str = "owner/repo1",
    open_issues: int = 10,
    open_prs: int = 3,
    workflows: list[WorkflowStatus] | None = None,
    issues_by_age: dict[int, int] | None = None,
    prs_by_age: dict[int, int] | None = None,
    branches_by_age: dict[int, int] | None = None,
) -> RepositoryStats:
    return RepositoryStats(
        full_name=name,
        default_branch="main",
        open_issues=open_issues,
        stale_issues=2,
        open_pull_requests=open_prs,
        stale_pull_requests=1,
        workflows=workflows or [],
        total_branches=5,
        stale_branches=1,
        issues_by_age=issues_by_age or {7: 8, 14: 6, 30: 4, 60: 2, 90: 1, 180: 0, 365: 0},
        prs_by_age=prs_by_age or {7: 2, 14: 1, 30: 0, 60: 0, 90: 0, 180: 0, 365: 0},
        branches_by_age=branches_by_age or {7: 4, 14: 3, 30: 2, 60: 1, 90: 1, 180: 0, 365: 0},
        fetched_at=datetime.now(UTC),
    )


def _snapshot(
    repo: str = "owner/repo1",
    snapshot_date: date | None = None,
    open_issues: int = 10,
    stale_issues: int = 2,
    open_prs: int = 3,
    stale_prs: int = 1,
    issues_by_age: dict | None = None,
    prs_by_age: dict | None = None,
    branches_by_age: dict | None = None,
) -> StatsSnapshot:
    return StatsSnapshot(
        snapshot_date=snapshot_date or date.today(),
        timestamp=datetime.now(UTC),
        repo_full_name=repo,
        open_issues=open_issues,
        stale_issues=stale_issues,
        open_prs=open_prs,
        stale_prs=stale_prs,
        workflow_total=2,
        workflow_failures=1,
        total_branches=5,
        stale_branches=1,
        issues_by_age_json=json.dumps(issues_by_age or {"7": 8, "30": 4, "365": 0}),
        prs_by_age_json=json.dumps(prs_by_age or {"7": 2, "30": 0}),
        branches_by_age_json=json.dumps(branches_by_age or {"30": 2, "90": 1}),
    )


# ---------------------------------------------------------------------------
# _compute_age_buckets
# ---------------------------------------------------------------------------


class TestComputeAgeBuckets:
    def test_empty(self) -> None:
        result = _compute_age_buckets([], datetime.now(UTC))
        assert all(v == 0 for v in result.values())
        assert set(result.keys()) == set(AGE_BUCKET_THRESHOLDS)

    def test_all_recent(self) -> None:
        now = datetime.now(UTC)
        dates = [now - timedelta(days=1), now - timedelta(days=3)]
        result = _compute_age_buckets(dates, now)
        assert result[7] == 0
        assert result[14] == 0

    def test_mixed_ages(self) -> None:
        now = datetime.now(UTC)
        dates = [
            now - timedelta(days=5),  # < 7
            now - timedelta(days=10),  # >= 7, < 14
            now - timedelta(days=35),  # >= 30, < 60
            now - timedelta(days=400),  # >= 365
        ]
        result = _compute_age_buckets(dates, now)
        assert result[7] == 3  # 10d, 35d, 400d
        assert result[14] == 2  # 35d, 400d
        assert result[30] == 2  # 35d, 400d
        assert result[60] == 1  # 400d
        assert result[365] == 1  # 400d

    def test_none_dates_treated_as_infinite(self) -> None:
        now = datetime.now(UTC)
        dates: list[datetime | None] = [None, now - timedelta(days=1)]
        result = _compute_age_buckets(dates, now)
        assert result[7] == 1  # None counts as inf
        assert result[365] == 1


# ---------------------------------------------------------------------------
# _pick_bucket
# ---------------------------------------------------------------------------


class TestPickBucket:
    def test_exact_match(self) -> None:
        assert _pick_bucket(30) == 30
        assert _pick_bucket(365) == 365

    def test_nearest(self) -> None:
        assert _pick_bucket(45) == 30 or _pick_bucket(45) == 60  # equidistant
        assert _pick_bucket(20) == 14
        assert _pick_bucket(100) == 90

    def test_below_minimum(self) -> None:
        assert _pick_bucket(3) == 7

    def test_above_maximum(self) -> None:
        assert _pick_bucket(500) == 365


# ---------------------------------------------------------------------------
# Snapshot recording (save_stats_to_db)
# ---------------------------------------------------------------------------


class TestSnapshotRecording:
    async def test_snapshot_created(self, engine: AsyncEngine) -> None:
        await save_stats_to_db(engine, [_stats()], [_repo()])
        async with AsyncSession(engine) as session:
            rows = (await session.exec(select(StatsSnapshot))).all()
        assert len(rows) == 1
        assert rows[0].repo_full_name == "owner/repo1"
        assert rows[0].open_issues == 10
        assert rows[0].stale_issues == 2
        assert rows[0].stale_prs == 1
        assert rows[0].snapshot_date == date.today()

    async def test_upsert_same_day(self, engine: AsyncEngine) -> None:
        """Multiple saves on the same day update the same row."""
        await save_stats_to_db(engine, [_stats(open_issues=10)], [_repo()])
        await save_stats_to_db(engine, [_stats(open_issues=20)], [_repo()])
        async with AsyncSession(engine) as session:
            rows = (await session.exec(select(StatsSnapshot))).all()
        assert len(rows) == 1
        assert rows[0].open_issues == 20  # updated

    async def test_age_buckets_persisted(self, engine: AsyncEngine) -> None:
        age = {7: 5, 14: 3, 30: 2, 60: 1, 90: 0, 180: 0, 365: 0}
        await save_stats_to_db(engine, [_stats(issues_by_age=age)], [_repo()])
        async with AsyncSession(engine) as session:
            snap = (await session.exec(select(StatsSnapshot))).first()
        assert snap is not None
        assert json.loads(snap.issues_by_age_json) == {str(k): v for k, v in age.items()}

    async def test_workflow_metrics(self, engine: AsyncEngine) -> None:
        wfs = [
            WorkflowStatus(name="CI", branch="main", status="success", url=""),
            WorkflowStatus(name="Deploy", branch="main", status="failure", url=""),
        ]
        await save_stats_to_db(engine, [_stats(workflows=wfs)], [_repo()])
        async with AsyncSession(engine) as session:
            snap = (await session.exec(select(StatsSnapshot))).first()
        assert snap is not None
        assert snap.workflow_total == 2
        assert snap.workflow_failures == 1

    async def test_multiple_repos(self, engine: AsyncEngine) -> None:
        repos = [_repo("a/b"), _repo("c/d")]
        stats = [_stats("a/b", open_issues=5), _stats("c/d", open_issues=15)]
        await save_stats_to_db(engine, stats, repos)
        async with AsyncSession(engine) as session:
            rows = (await session.exec(select(StatsSnapshot))).all()
        assert len(rows) == 2
        by_name = {r.repo_full_name: r for r in rows}
        assert by_name["a/b"].open_issues == 5
        assert by_name["c/d"].open_issues == 15


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


class TestRetention:
    async def test_old_snapshots_deleted(self, engine: AsyncEngine) -> None:
        """Snapshots older than retention_days are deleted."""
        # Manually insert an old snapshot
        old_date = date.today() - timedelta(days=100)
        async with AsyncSession(engine) as session:
            session.add(
                StatsSnapshot(
                    snapshot_date=old_date,
                    timestamp=datetime.now(UTC),
                    repo_full_name="owner/repo1",
                    open_issues=5,
                )
            )
            await session.commit()

        # Save with retention=90 — the old snapshot should be deleted
        await save_stats_to_db(engine, [_stats()], [_repo()], retention_days=90)
        async with AsyncSession(engine) as session:
            rows = (await session.exec(select(StatsSnapshot))).all()
        dates = {r.snapshot_date for r in rows}
        assert old_date not in dates
        assert date.today() in dates

    async def test_recent_snapshots_kept(self, engine: AsyncEngine) -> None:
        """Snapshots within retention window are preserved."""
        recent_date = date.today() - timedelta(days=10)
        async with AsyncSession(engine) as session:
            session.add(
                StatsSnapshot(
                    snapshot_date=recent_date,
                    timestamp=datetime.now(UTC),
                    repo_full_name="other/repo",
                    open_issues=3,
                )
            )
            await session.commit()

        await save_stats_to_db(engine, [_stats()], [_repo()], retention_days=90)
        async with AsyncSession(engine) as session:
            rows = (await session.exec(select(StatsSnapshot))).all()
        dates = {r.snapshot_date for r in rows}
        assert recent_date in dates


# ---------------------------------------------------------------------------
# History API helpers (series building)
# ---------------------------------------------------------------------------


class TestBuildSeries:
    def test_extract_stale_series_exact_bucket(self) -> None:
        snaps = [_snapshot(issues_by_age={"7": 10, "30": 5, "365": 1})]
        result = _extract_stale_series(snaps, "issues_by_age_json", 30)
        assert result == [5]

    def test_extract_stale_series_nearest_bucket(self) -> None:
        snaps = [_snapshot(issues_by_age={"7": 10, "14": 8, "30": 5})]
        result = _extract_stale_series(snaps, "issues_by_age_json", 20)
        # 20 is nearest to 14
        assert result == [8]

    def test_build_series_complete(self) -> None:
        snaps = [_snapshot(), _snapshot(snapshot_date=date.today() - timedelta(days=1))]
        series = _build_series(snaps)
        assert "open_issues" in series
        assert "stale_issues" in series
        assert "open_prs" in series
        assert "stale_prs" in series
        assert "workflow_total" in series
        assert "workflow_failures" in series
        assert "total_branches" in series
        assert "stale_branches" in series
        assert "backlog_total" in series
        assert len(series["open_issues"]) == 2

    def test_build_series_uses_direct_stale_counts(self) -> None:
        snap = _snapshot()
        snap.stale_issues = 7
        snap.stale_prs = 3
        snap.stale_branches = 2
        series = _build_series([snap])
        assert series["stale_issues"] == [7]
        assert series["stale_prs"] == [3]
        assert series["stale_branches"] == [2]

    def test_build_series_backlog_total(self) -> None:
        snap = _snapshot()
        snap.workflow_failures = 2
        snap.stale_prs = 3
        snap.stale_issues = 1
        snap.stale_branches = 4
        snap.check_failures = 5
        snap.check_warnings = 1
        series = _build_series([snap])
        assert series["backlog_total"] == [2 + 3 + 1 + 4 + 5 + 1]


# ---------------------------------------------------------------------------
# History API endpoints
# ---------------------------------------------------------------------------


class TestHistoryAPI:
    async def test_global_empty(self, engine: AsyncEngine) -> None:
        from grimoire.history.router import history_global

        set_history_state(engine, StalenessConfig())
        result = await history_global(days=30)
        assert result["timestamps"] == []
        assert result["series"] == {}

    async def test_global_with_data(self, engine: AsyncEngine) -> None:
        from grimoire.history.router import history_global

        set_history_state(engine, StalenessConfig(issues_days=30))

        # Insert test data
        today = date.today()
        async with AsyncSession(engine) as session:
            session.add(
                StatsSnapshot(
                    snapshot_date=today,
                    timestamp=datetime.now(UTC),
                    repo_full_name="a/b",
                    open_issues=10,
                    stale_issues=4,
                    open_prs=3,
                    stale_prs=1,
                    workflow_total=4,
                    workflow_failures=1,
                    total_branches=8,
                    stale_branches=2,
                    issues_by_age_json=json.dumps({"7": 8, "30": 5, "365": 1}),
                    prs_by_age_json=json.dumps({"7": 2, "30": 1}),
                    branches_by_age_json=json.dumps({"30": 3, "90": 2}),
                )
            )
            session.add(
                StatsSnapshot(
                    snapshot_date=today,
                    timestamp=datetime.now(UTC),
                    repo_full_name="c/d",
                    open_issues=5,
                    stale_issues=2,
                    open_prs=1,
                    stale_prs=0,
                    workflow_total=2,
                    workflow_failures=0,
                    total_branches=3,
                    stale_branches=0,
                    issues_by_age_json=json.dumps({"7": 4, "30": 2, "365": 0}),
                    prs_by_age_json=json.dumps({"7": 1, "30": 0}),
                    branches_by_age_json=json.dumps({"30": 1, "90": 0}),
                )
            )
            await session.commit()

        result = await history_global(days=30)
        assert len(result["timestamps"]) == 1
        assert result["series"]["open_issues"] == [15]  # 10 + 5
        assert result["series"]["stale_issues"] == [6]  # 4 + 2
        assert result["series"]["open_prs"] == [4]  # 3 + 1
        assert result["series"]["stale_prs"] == [1]  # 1 + 0
        assert result["series"]["workflow_total"] == [6]  # 4 + 2
        assert result["series"]["workflow_failures"] == [1]

    async def test_repo_endpoint(self, engine: AsyncEngine) -> None:
        from grimoire.history.router import history_repo

        set_history_state(engine, StalenessConfig())

        today = date.today()
        yesterday = today - timedelta(days=1)
        async with AsyncSession(engine) as session:
            for d, issues in [(yesterday, 8), (today, 10)]:
                session.add(
                    StatsSnapshot(
                        snapshot_date=d,
                        timestamp=datetime.now(UTC),
                        repo_full_name="owner/repo",
                        open_issues=issues,
                        issues_by_age_json="{}",
                        prs_by_age_json="{}",
                        branches_by_age_json="{}",
                    )
                )
            await session.commit()

        result = await history_repo("owner/repo", days=30)
        assert len(result["timestamps"]) == 2
        assert result["series"]["open_issues"] == [8, 10]

    async def test_repo_not_found(self, engine: AsyncEngine) -> None:
        from grimoire.history.router import history_repo

        set_history_state(engine, StalenessConfig())
        result = await history_repo("nonexistent/repo", days=30)
        assert result["timestamps"] == []

    async def test_days_filter(self, engine: AsyncEngine) -> None:
        from grimoire.history.router import history_repo

        set_history_state(engine, StalenessConfig())

        # Insert data 10 days ago and today
        async with AsyncSession(engine) as session:
            for d in [date.today() - timedelta(days=10), date.today()]:
                session.add(
                    StatsSnapshot(
                        snapshot_date=d,
                        timestamp=datetime.now(UTC),
                        repo_full_name="owner/repo",
                        open_issues=5,
                        issues_by_age_json="{}",
                        prs_by_age_json="{}",
                        branches_by_age_json="{}",
                    )
                )
            await session.commit()

        # With days=7, only today should be returned
        result = await history_repo("owner/repo", days=7)
        assert len(result["timestamps"]) == 1

        # With days=30, both should be returned
        result = await history_repo("owner/repo", days=30)
        assert len(result["timestamps"]) == 2

    async def test_global_repos_filter(self, engine: AsyncEngine) -> None:
        """When repos param is provided, only those repos are aggregated."""
        from grimoire.history.router import history_global

        set_history_state(engine, StalenessConfig(issues_days=30))

        today = date.today()
        async with AsyncSession(engine) as session:
            for repo, issues, prs in [("a/b", 10, 3), ("c/d", 5, 1), ("e/f", 8, 2)]:
                session.add(
                    StatsSnapshot(
                        snapshot_date=today,
                        timestamp=datetime.now(UTC),
                        repo_full_name=repo,
                        open_issues=issues,
                        open_prs=prs,
                        workflow_total=2,
                        workflow_failures=0,
                        total_branches=4,
                        stale_branches=0,
                        issues_by_age_json=json.dumps({"30": issues}),
                        prs_by_age_json="{}",
                        branches_by_age_json="{}",
                    )
                )
            await session.commit()

        # No filter → all repos
        result = await history_global(days=30, repos=None)
        assert result["series"]["open_issues"] == [23]  # 10 + 5 + 8

        # Filter to one repo
        result = await history_global(days=30, repos=["a/b"])
        assert result["series"]["open_issues"] == [10]
        assert result["series"]["open_prs"] == [3]

        # Filter to two repos
        result = await history_global(days=30, repos=["a/b", "c/d"])
        assert result["series"]["open_issues"] == [15]  # 10 + 5
        assert result["series"]["open_prs"] == [4]  # 3 + 1

    async def test_global_repos_filter_unknown(self, engine: AsyncEngine) -> None:
        """Unknown repo names return empty results."""
        from grimoire.history.router import history_global

        set_history_state(engine, StalenessConfig())

        today = date.today()
        async with AsyncSession(engine) as session:
            session.add(
                StatsSnapshot(
                    snapshot_date=today,
                    timestamp=datetime.now(UTC),
                    repo_full_name="a/b",
                    open_issues=10,
                    issues_by_age_json="{}",
                    prs_by_age_json="{}",
                    branches_by_age_json="{}",
                )
            )
            await session.commit()

        result = await history_global(days=30, repos=["nonexistent/repo"])
        assert result["timestamps"] == []
        assert result["series"] == {}

    async def test_global_repos_empty_list(self, engine: AsyncEngine) -> None:
        """Empty repos list behaves like no filter (all repos)."""
        from grimoire.history.router import history_global

        set_history_state(engine, StalenessConfig())

        today = date.today()
        async with AsyncSession(engine) as session:
            session.add(
                StatsSnapshot(
                    snapshot_date=today,
                    timestamp=datetime.now(UTC),
                    repo_full_name="a/b",
                    open_issues=10,
                    issues_by_age_json="{}",
                    prs_by_age_json="{}",
                    branches_by_age_json="{}",
                )
            )
            await session.commit()

        # Empty list should not filter
        result = await history_global(days=30, repos=[])
        assert result["series"]["open_issues"] == [10]
