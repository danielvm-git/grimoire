"""Tests for the Backlog feature — priority engine and web routes."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from grimoire.config import (
    BacklogCategoryWeights,
    BacklogConfig,
    RepositoryWeightRule,
    StalenessConfig,
)
from grimoire.models import (
    IssueDetail,
    PullRequestDetail,
    RepositoryStats,
    TrackedRepository,
    WorkflowStatus,
)
from grimoire.web.backlog import (
    BacklogCategory,
    BacklogItem,
    _compute_age_factor,
    _days_since,
    _format_age,
    build_backlog_items,
    compute_score,
    export_markdown,
    resolve_repo_weight,
)

# ---------------------------------------------------------------------------
# Unit tests for priority scoring
# ---------------------------------------------------------------------------


class TestComputeScore:
    """Tests for the priority score computation."""

    def _default_config(self, **overrides: float) -> BacklogConfig:
        return BacklogConfig(
            category_weights=BacklogCategoryWeights(**overrides),
        )

    def test_default_weights_workflow(self) -> None:
        config = self._default_config()
        score = compute_score(
            BacklogCategory.FAILING_WORKFLOW,
            repo_weight=1.0,
            age_days=0.0,
            reference_days=1.0,
            config=config,
        )
        assert score == 100.0  # 100 * 1.0 * 1.0 (age_factor for 0 days)

    def test_repo_priority_multiplier(self) -> None:
        config = self._default_config()
        score = compute_score(
            BacklogCategory.FAILING_WORKFLOW,
            repo_weight=3.0,
            age_days=0.0,
            reference_days=1.0,
            config=config,
        )
        assert score == 300.0

    def test_zero_repo_priority_hides_items(self) -> None:
        config = self._default_config()
        score = compute_score(
            BacklogCategory.FAILING_WORKFLOW,
            repo_weight=0.0,
            age_days=10.0,
            reference_days=1.0,
            config=config,
        )
        assert score == 0.0

    def test_age_factor_increases_score(self) -> None:
        config = self._default_config()
        score_fresh = compute_score(
            BacklogCategory.STALE_PR,
            repo_weight=1.0,
            age_days=0.0,
            reference_days=30.0,
            config=config,
        )
        score_old = compute_score(
            BacklogCategory.STALE_PR,
            repo_weight=1.0,
            age_days=30.0,
            reference_days=30.0,
            config=config,
        )
        assert score_old > score_fresh
        # At exactly reference_days, age_factor should be 1 + log2(2) = 2.0
        assert score_old == pytest.approx(50.0 * 2.0)

    def test_workflow_weight_override(self) -> None:
        config = BacklogConfig(
            workflow_weights={"Release *": 2.0},
        )
        score = compute_score(
            BacklogCategory.FAILING_WORKFLOW,
            repo_weight=1.0,
            age_days=0.0,
            reference_days=1.0,
            config=config,
            workflow_name="Release Deploy",
        )
        assert score == 200.0  # 100 * 1.0 * 2.0

    def test_workflow_weight_no_match_uses_default(self) -> None:
        config = BacklogConfig(
            workflow_weights={"Release *": 2.0},
        )
        score = compute_score(
            BacklogCategory.FAILING_WORKFLOW,
            repo_weight=1.0,
            age_days=0.0,
            reference_days=1.0,
            config=config,
            workflow_name="CI",
        )
        assert score == 100.0

    def test_custom_category_weight(self) -> None:
        config = self._default_config(stale_issue=5.0)
        score = compute_score(
            BacklogCategory.STALE_ISSUE,
            repo_weight=1.0,
            age_days=0.0,
            reference_days=365.0,
            config=config,
        )
        assert score == 5.0


class TestAgeFactor:
    """Tests for the age factor calculation."""

    def test_zero_age(self) -> None:
        assert _compute_age_factor(0.0, 30.0) == 1.0

    def test_at_reference(self) -> None:
        factor = _compute_age_factor(30.0, 30.0)
        assert factor == pytest.approx(1.0 + math.log2(2.0))

    def test_negative_reference_clamped(self) -> None:
        # Should not crash; treats reference as 1.0
        factor = _compute_age_factor(5.0, -10.0)
        assert factor > 1.0


class TestFormatAge:
    """Tests for the age formatting utility."""

    def test_less_than_day(self) -> None:
        assert _format_age(0.5) == "<1d"

    def test_days(self) -> None:
        assert _format_age(45.0) == "45d"

    def test_years(self) -> None:
        assert _format_age(365.0) == "1y"

    def test_years_and_days(self) -> None:
        assert _format_age(400.0) == "1y 35d"


class TestDaysSince:
    """Tests for the _days_since helper."""

    def test_none_returns_zero(self) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        assert _days_since(None, now) == 0.0

    def test_naive_datetime_treated_as_utc(self) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        dt = datetime(2026, 4, 1)  # naive
        result = _days_since(dt, now)
        assert result == 30.0

    def test_future_date_returns_zero(self) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        dt = datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert _days_since(dt, now) == 0.0


class TestResolveRepoWeight:
    """Tests for resolve_repo_weight()."""

    def test_no_rules_returns_default(self) -> None:
        config = BacklogConfig()
        assert resolve_repo_weight("org/repo", config) == 1.0

    def test_regex_match(self) -> None:
        config = BacklogConfig(
            repository_weights=[RepositoryWeightRule(regex="org/*", weight=3.0)],
        )
        assert resolve_repo_weight("org/repo", config) == 3.0

    def test_repos_list_match(self) -> None:
        config = BacklogConfig(
            repository_weights=[
                RepositoryWeightRule(repos=["org/important"], weight=5.0),
            ],
        )
        assert resolve_repo_weight("org/important", config) == 5.0
        assert resolve_repo_weight("org/other", config) == 1.0

    def test_last_match_wins(self) -> None:
        config = BacklogConfig(
            repository_weights=[
                RepositoryWeightRule(regex="*", weight=2.0),
                RepositoryWeightRule(repos=["org/special"], weight=10.0),
            ],
        )
        assert resolve_repo_weight("org/special", config) == 10.0
        assert resolve_repo_weight("org/other", config) == 2.0

    def test_no_match_returns_default(self) -> None:
        config = BacklogConfig(
            repository_weights=[
                RepositoryWeightRule(repos=["org/specific"], weight=5.0),
            ],
        )
        assert resolve_repo_weight("other/repo", config) == 1.0


# ---------------------------------------------------------------------------
# Unit tests for item collection
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _make_repo(name: str = "acme/api", branches: list[str] | None = None) -> TrackedRepository:
    return TrackedRepository(
        full_name=name,
        default_branch="main",
        branches=branches or ["main"],
        source="static",
    )


def _make_stats(
    name: str = "acme/api",
    workflows: list[WorkflowStatus] | None = None,
    stale_pr_items: list[PullRequestDetail] | None = None,
    stale_issue_items: list[IssueDetail] | None = None,
    stale_branches: int = 0,
) -> RepositoryStats:
    return RepositoryStats(
        full_name=name,
        default_branch="main",
        workflows=workflows or [],
        stale_pr_items=stale_pr_items or [],
        stale_issue_items=stale_issue_items or [],
        stale_branches=stale_branches,
        fetched_at=NOW,
    )


class TestBuildBacklogItems:
    """Tests for the full backlog item builder."""

    def test_empty_cache(self) -> None:
        items = build_backlog_items(
            cache={},
            repos={},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert items == []

    def test_failing_workflow_creates_item(self) -> None:
        wf = WorkflowStatus(
            name="CI",
            branch="main",
            status="failure",
            url="https://github.com/acme/api/actions",
            run_url="https://github.com/acme/api/actions/runs/42",
        )
        repo = _make_repo()
        stats = _make_stats(workflows=[wf])
        items = build_backlog_items(
            cache={repo.full_name: stats},
            repos={repo.full_name: repo},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert len(items) == 1
        assert items[0].category == BacklogCategory.FAILING_WORKFLOW
        assert "CI" in items[0].description
        assert items[0].url == "https://github.com/acme/api/actions/runs/42"
        assert items[0].score == 100.0

    def test_passing_workflow_not_included(self) -> None:
        wf = WorkflowStatus(name="CI", branch="main", status="success", url="")
        repo = _make_repo()
        stats = _make_stats(workflows=[wf])
        items = build_backlog_items(
            cache={repo.full_name: stats},
            repos={repo.full_name: repo},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert len(items) == 0

    def test_stale_pr_creates_item(self) -> None:
        pr = PullRequestDetail(
            number=99,
            title="Fix auth",
            url="https://github.com/acme/api/pull/99",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            last_activity_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            author="alice",
        )
        repo = _make_repo()
        stats = _make_stats(stale_pr_items=[pr])
        items = build_backlog_items(
            cache={repo.full_name: stats},
            repos={repo.full_name: repo},
            config=BacklogConfig(),
            staleness=StalenessConfig(pull_requests_days=30),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert len(items) == 1
        assert items[0].category == BacklogCategory.STALE_PR
        assert items[0].number == 99
        # Age is ~61 days, excess over 30d threshold is ~31d
        assert items[0].age_days == pytest.approx(61.0, abs=1.0)

    def test_stale_issue_creates_item(self) -> None:
        issue = IssueDetail(
            number=42,
            title="Old bug",
            url="https://github.com/acme/api/issues/42",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_activity_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        repo = _make_repo()
        stats = _make_stats(stale_issue_items=[issue])
        items = build_backlog_items(
            cache={repo.full_name: stats},
            repos={repo.full_name: repo},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert len(items) == 1
        assert items[0].category == BacklogCategory.STALE_ISSUE
        assert items[0].number == 42

    def test_stale_branches_summary_item(self) -> None:
        repo = _make_repo()
        stats = _make_stats(stale_branches=5)
        items = build_backlog_items(
            cache={repo.full_name: stats},
            repos={repo.full_name: repo},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert len(items) == 1
        assert items[0].category == BacklogCategory.STALE_BRANCHES
        assert "5 stale branches" in items[0].description
        assert items[0].url.endswith("/branches/stale")

    def test_stale_branches_count_affects_score(self) -> None:
        repo = _make_repo()
        stats1 = _make_stats(name="acme/api", stale_branches=1)
        stats8 = _make_stats(name="acme/big", stale_branches=8)
        items1 = build_backlog_items(
            cache={"acme/api": stats1},
            repos={"acme/api": repo},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        repo_big = _make_repo(name="acme/big")
        items8 = build_backlog_items(
            cache={"acme/big": stats8},
            repos={"acme/big": repo_big},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert items8[0].score > items1[0].score

    def test_items_sorted_by_score_descending(self) -> None:
        """Multiple item types should be sorted highest-score-first."""
        wf = WorkflowStatus(name="CI", branch="main", status="failure", url="", run_url="")
        issue = IssueDetail(
            number=1,
            title="Old",
            url="",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        repo = _make_repo()
        stats = _make_stats(workflows=[wf], stale_issue_items=[issue])
        items = build_backlog_items(
            cache={repo.full_name: stats},
            repos={repo.full_name: repo},
            config=BacklogConfig(),
            staleness=StalenessConfig(),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert len(items) == 2
        assert items[0].score >= items[1].score
        assert items[0].category == BacklogCategory.FAILING_WORKFLOW

    def test_repo_priority_affects_ranking(self) -> None:
        """A low-weight repo's workflow should rank below a high-weight repo's stale PR."""
        wf = WorkflowStatus(name="CI", branch="main", status="failure", url="", run_url="")
        pr = PullRequestDetail(
            number=1,
            title="PR",
            url="",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            last_activity_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        low_repo = _make_repo(name="low/repo")
        high_repo = _make_repo(name="high/repo")
        low_stats = _make_stats(name="low/repo", workflows=[wf])
        high_stats = _make_stats(name="high/repo", stale_pr_items=[pr])

        config = BacklogConfig(
            repository_weights=[
                RepositoryWeightRule(regex="low/*", weight=0.3),
                RepositoryWeightRule(regex="high/*", weight=5.0),
            ],
        )
        items = build_backlog_items(
            cache={"low/repo": low_stats, "high/repo": high_stats},
            repos={"low/repo": low_repo, "high/repo": high_repo},
            config=config,
            staleness=StalenessConfig(pull_requests_days=30),
            check_targets={},
            results_by_key={},
            check_defs=[],
            now=NOW,
        )
        assert len(items) == 2
        assert items[0].repo_full_name == "high/repo"


# ---------------------------------------------------------------------------
# Tests for BacklogItem properties
# ---------------------------------------------------------------------------


class TestBacklogItem:
    """Tests for BacklogItem tier and rendering methods."""

    def test_tier_critical(self) -> None:
        item = BacklogItem(
            category=BacklogCategory.FAILING_WORKFLOW,
            repo_full_name="a/b",
            description="x",
            url="",
            age_days=0,
            score=100,
        )
        assert item.tier == "critical"
        assert item.tier_class == "error"

    def test_tier_high(self) -> None:
        item = BacklogItem(
            category=BacklogCategory.STALE_PR,
            repo_full_name="a/b",
            description="x",
            url="",
            age_days=0,
            score=60,
        )
        assert item.tier == "high"

    def test_tier_medium(self) -> None:
        item = BacklogItem(
            category=BacklogCategory.STALE_ISSUE,
            repo_full_name="a/b",
            description="x",
            url="",
            age_days=0,
            score=25,
        )
        assert item.tier == "medium"

    def test_tier_low(self) -> None:
        item = BacklogItem(
            category=BacklogCategory.STALE_BRANCHES,
            repo_full_name="a/b",
            description="x",
            url="",
            age_days=0,
            score=5,
        )
        assert item.tier == "low"

    def test_to_markdown_with_url(self) -> None:
        item = BacklogItem(
            category=BacklogCategory.FAILING_WORKFLOW,
            repo_full_name="acme/api",
            description="CI failing on `main`",
            url="https://github.com/acme/api/runs/1",
            age_days=3.0,
            score=100,
        )
        md = item.to_markdown()
        assert md.startswith("- [ ] **[acme/api]**")
        assert "[View](" in md
        assert "(3d)" in md

    def test_to_markdown_without_url(self) -> None:
        item = BacklogItem(
            category=BacklogCategory.FAILING_CHECK_ERROR,
            repo_full_name="acme/api",
            description="Check 'lint' failing on `main`",
            url="",
            age_days=0.0,
            score=80,
        )
        md = item.to_markdown()
        assert "[View]" not in md

    def test_to_markdown_escapes_special_chars(self) -> None:
        item = BacklogItem(
            category=BacklogCategory.STALE_PR,
            repo_full_name="acme/api",
            description="PR #1: Fix [brackets] and (parens)",
            url="https://example.com",
            age_days=30.0,
            score=50,
        )
        md = item.to_markdown()
        assert "\\[brackets\\]" in md
        assert "\\(parens\\)" in md


# ---------------------------------------------------------------------------
# Tests for Markdown export
# ---------------------------------------------------------------------------


class TestExportMarkdown:
    """Tests for the full Markdown export."""

    def test_empty_list(self) -> None:
        md = export_markdown([], title_date="2026-05-01")
        assert "# Grimoire Backlog — 2026-05-01" in md
        assert "## " not in md  # no tier sections

    def test_groups_by_tier(self) -> None:
        items = [
            BacklogItem(
                category=BacklogCategory.FAILING_WORKFLOW,
                repo_full_name="a/b",
                description="wf fail",
                url="",
                age_days=0,
                score=100,
            ),
            BacklogItem(
                category=BacklogCategory.STALE_ISSUE,
                repo_full_name="a/b",
                description="old issue",
                url="",
                age_days=0,
                score=15,
            ),
        ]
        md = export_markdown(items, title_date="2026-05-01")
        assert "## Critical (1 item)" in md
        assert "## Low (1 item)" in md

    def test_items_within_tiers(self) -> None:
        items = [
            BacklogItem(
                category=BacklogCategory.FAILING_WORKFLOW,
                repo_full_name="a/b",
                description="CI fail",
                url="http://x",
                age_days=0,
                score=100,
            ),
            BacklogItem(
                category=BacklogCategory.FAILING_CHECK_ERROR,
                repo_full_name="a/c",
                description="lint fail",
                url="",
                age_days=0,
                score=80,
            ),
        ]
        md = export_markdown(items, title_date="2026-05-01")
        assert "## Critical (2 items)" in md
        assert "**[a/b]**" in md
        assert "**[a/c]**" in md


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


class TestBacklogRoute:
    """Tests for the /backlog page route."""

    async def test_backlog_page_renders(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/backlog")
        assert resp.status_code == 200
        assert "Backlog" in resp.text

    async def test_backlog_page_shows_failing_workflow(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/backlog")
        assert resp.status_code == 200
        # acme/frontend has a failing Build workflow
        assert "acme/frontend" in resp.text
        assert "Build" in resp.text

    async def test_backlog_page_shows_stale_items(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/backlog")
        assert resp.status_code == 200
        # acme/api has stale PRs, issues, and branches
        assert "acme/api" in resp.text

    async def test_backlog_page_shows_stale_branches(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/backlog")
        assert resp.status_code == 200
        assert "stale branch" in resp.text

    async def test_backlog_items_partial(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/backlog-items")
        assert resp.status_code == 200
        # Should contain items
        assert "acme/" in resp.text

    async def test_backlog_items_partial_filter_by_category(
        self,
        web_client: AsyncClient,
    ) -> None:
        resp = await web_client.get("/partials/backlog-items?categories=failing_workflow")
        assert resp.status_code == 200
        assert "Build" in resp.text
        # Should not show stale items
        assert "stale branch" not in resp.text

    async def test_backlog_items_partial_filter_by_repo(
        self,
        web_client: AsyncClient,
    ) -> None:
        resp = await web_client.get("/partials/backlog-items?repos=acme/frontend")
        assert resp.status_code == 200
        assert "acme/frontend" in resp.text
        # Should not show items from acme/api
        assert "acme/api" not in resp.text

    async def test_backlog_export_markdown(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/api/backlog/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/markdown")
        assert "# Grimoire Backlog" in resp.text
        assert "- [ ]" in resp.text

    async def test_backlog_page_with_checks(
        self,
        web_client_with_checks: AsyncClient,
    ) -> None:
        resp = await web_client_with_checks.get("/backlog")
        assert resp.status_code == 200
        # Should show the failing watchdog check for acme/frontend
        assert "Watchdog" in resp.text
