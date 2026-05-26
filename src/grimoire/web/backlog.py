"""Backlog: priority computation, item collection, and Markdown export."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grimoire.config import BacklogConfig, StalenessConfig
    from grimoire.models import (
        RepositoryStats,
        TrackedRepository,
    )


class BacklogCategory(str, Enum):
    """Problem categories for backlog items."""

    FAILING_WORKFLOW = "failing_workflow"
    FAILING_CHECK_ERROR = "failing_check_error"
    FAILING_CHECK_WARNING = "failing_check_warning"
    STALE_PR = "stale_pr"
    STALE_ISSUE = "stale_issue"


# Labels and icons used in templates
CATEGORY_DISPLAY = {
    BacklogCategory.FAILING_WORKFLOW: ("Failing Workflow", "fa-solid fa-gear"),
    BacklogCategory.FAILING_CHECK_ERROR: ("Failing Check", "fa-solid fa-clipboard-check"),
    BacklogCategory.FAILING_CHECK_WARNING: ("Check Warning", "fa-solid fa-clipboard-check"),
    BacklogCategory.STALE_PR: ("Stale PR", "fa-solid fa-code-pull-request"),
    BacklogCategory.STALE_ISSUE: ("Stale Issue", "fa-solid fa-circle-exclamation"),
}

# Priority tier thresholds (score → tier name)
PRIORITY_TIERS = [
    (80, "critical", "error"),
    (50, "high", "warning"),
    (20, "medium", "info"),
    (0, "low", "ghost"),
]

# Tier → (FontAwesome arrow icon, DaisyUI text color class)
TIER_DISPLAY = {
    "critical": ("fa-solid fa-angles-up", "text-error"),
    "high": ("fa-solid fa-angle-up", "text-warning"),
    "medium": ("fa-solid fa-minus", "text-info"),
    "low": ("fa-solid fa-angle-down", "opacity-40"),
}


@dataclass
class BacklogItem:
    """A single prioritised problem in the backlog."""

    category: BacklogCategory
    repo_full_name: str
    description: str
    url: str  # link to GitHub (workflow run, PR, issue, branches page)
    age_days: float
    score: float = 0.0
    # Extra context for rendering
    branch: str = ""
    number: int = 0  # PR or issue number

    @property
    def category_label(self) -> str:
        return CATEGORY_DISPLAY[self.category][0]

    @property
    def category_icon(self) -> str:
        return CATEGORY_DISPLAY[self.category][1]

    @property
    def tier(self) -> str:
        for threshold, tier_name, _ in PRIORITY_TIERS:
            if self.score >= threshold:
                return tier_name
        return "low"

    @property
    def tier_class(self) -> str:
        """DaisyUI badge class for the priority tier."""
        for threshold, _, cls in PRIORITY_TIERS:
            if self.score >= threshold:
                return cls
        return "ghost"

    @property
    def tier_icon(self) -> str:
        """FontAwesome arrow icon for the priority tier."""
        return TIER_DISPLAY.get(self.tier, TIER_DISPLAY["low"])[0]

    @property
    def tier_color(self) -> str:
        """DaisyUI text color class for the priority tier."""
        return TIER_DISPLAY.get(self.tier, TIER_DISPLAY["low"])[1]

    @property
    def item_id(self) -> str:
        """Stable identifier for client-side dismiss tracking."""
        if self.number:
            return f"{self.category.value}:{self.repo_full_name}:#{self.number}"
        if self.branch:
            return f"{self.category.value}:{self.repo_full_name}:{self.branch}"
        return f"{self.category.value}:{self.repo_full_name}:{self.description[:60]}"

    def to_markdown(self) -> str:
        """Render this item as a single Markdown checklist line."""
        age = _format_age(self.age_days)
        desc = _escape_markdown(self.description)
        age_part = f" ({age})" if self.age_days > 0 else ""
        link_part = f" — [View]({self.url})" if self.url else ""
        return f"- [ ] **[{self.repo_full_name}]** {desc}{age_part}{link_part}"


def _escape_markdown(text: str) -> str:
    """Escape characters that break Markdown formatting in inline text."""
    for ch in ("\\", "[", "]", "(", ")", "`", "*", "_", "~"):
        text = text.replace(ch, f"\\{ch}")
    return text.replace("\n", " ")


def _format_age(age_days: float) -> str:
    """Human-readable age string."""
    days = int(age_days)
    if days == 0:
        return "<1d"
    if days < 365:
        return f"{days}d"
    years = days // 365
    remainder = days % 365
    if remainder == 0:
        return f"{years}y"
    return f"{years}y {remainder}d"


# ---------------------------------------------------------------------------
# Priority computation
# ---------------------------------------------------------------------------


def _get_category_weight(
    category: BacklogCategory,
    config: BacklogConfig,
) -> float:
    """Look up the base weight for a category from config."""
    weights = config.category_weights
    mapping = {
        BacklogCategory.FAILING_WORKFLOW: weights.failing_workflow,
        BacklogCategory.FAILING_CHECK_ERROR: weights.failing_check_error,
        BacklogCategory.FAILING_CHECK_WARNING: weights.failing_check_warning,
        BacklogCategory.STALE_PR: weights.stale_pr,
        BacklogCategory.STALE_ISSUE: weights.stale_issue,
    }
    return mapping.get(category, 1.0)


def _get_workflow_multiplier(
    workflow_name: str,
    config: BacklogConfig,
) -> float:
    """Look up per-workflow-name weight override (regex matching)."""
    for pattern, multiplier in config.workflow_weights.items():
        if re.search(pattern, workflow_name):
            return multiplier
    return 1.0


def resolve_repo_weight(
    full_name: str,
    config: BacklogConfig,
) -> float:
    """Resolve the backlog weight for a repository.

    Evaluates ``config.repository_weights`` top-to-bottom; last matching
    rule wins.  Returns 1.0 if no rule matches.
    """
    weight = 1.0
    for rule in config.repository_weights:
        if rule.repos is not None and full_name in rule.repos:
            weight = rule.weight
        elif rule.regex is not None and fnmatch(full_name, rule.regex):
            weight = rule.weight
    return weight


def _compute_age_factor(age_days: float, reference_days: float) -> float:
    """Gentle logarithmic boost for older problems.

    For stale items, pass *excess* days (age - threshold) so the factor starts
    at ~1.0 right when the item becomes stale and grows from there.

    Returns 1.0 for brand-new items, ~2× at ``reference_days`` excess, ~3× at 3×.
    """
    if reference_days <= 0:
        reference_days = 1.0
    return 1.0 + math.log2(1.0 + age_days / reference_days)


def compute_score(
    category: BacklogCategory,
    repo_weight: float,
    age_days: float,
    reference_days: float,
    config: BacklogConfig,
    workflow_name: str = "",
) -> float:
    """Compute the priority score for a backlog item."""
    category_weight = _get_category_weight(category, config)
    workflow_mult = _get_workflow_multiplier(workflow_name, config) if workflow_name else 1.0
    age_factor = _compute_age_factor(age_days, reference_days)
    return category_weight * repo_weight * workflow_mult * age_factor


# ---------------------------------------------------------------------------
# Item collection
# ---------------------------------------------------------------------------


def _days_since(dt: datetime | None, now: datetime) -> float:
    """Days elapsed since *dt*; returns 0 if *dt* is None."""
    if dt is None:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(delta.total_seconds() / 86400, 0.0)


def _collect_workflow_items(
    stats: RepositoryStats,
    repo: TrackedRepository,
    config: BacklogConfig,
    now: datetime,
) -> list[BacklogItem]:
    """Create backlog items for failing workflows.

    Workflow failures use age_factor=1.0 because we don't track when the
    failure first started — only that it's currently failing.
    """
    items: list[BacklogItem] = []
    for wf in stats.workflows:
        if wf.status != "failure":
            continue
        category_weight = _get_category_weight(BacklogCategory.FAILING_WORKFLOW, config)
        workflow_mult = _get_workflow_multiplier(wf.name, config)
        score = category_weight * resolve_repo_weight(repo.full_name, config) * workflow_mult
        items.append(
            BacklogItem(
                category=BacklogCategory.FAILING_WORKFLOW,
                repo_full_name=repo.full_name,
                description=f"Workflow '{wf.name}' failing on `{wf.branch}`",
                url=wf.run_url or wf.url,
                age_days=0.0,
                score=score,
                branch=wf.branch,
            )
        )
    return items


def _collect_stale_pr_items(
    stats: RepositoryStats,
    repo: TrackedRepository,
    config: BacklogConfig,
    staleness: StalenessConfig,
    now: datetime,
) -> list[BacklogItem]:
    """Create backlog items for stale pull requests."""
    items: list[BacklogItem] = []
    threshold = float(staleness.pull_requests_days)
    for pr in stats.stale_pr_items:
        if pr.number <= 0:
            continue
        age_days = _days_since(pr.last_activity_at or pr.created_at, now)
        excess = max(0.0, age_days - threshold)
        score = compute_score(
            BacklogCategory.STALE_PR,
            resolve_repo_weight(repo.full_name, config),
            excess,
            reference_days=threshold,
            config=config,
        )
        items.append(
            BacklogItem(
                category=BacklogCategory.STALE_PR,
                repo_full_name=repo.full_name,
                description=f"PR #{pr.number}: {pr.title}",
                url=pr.url,
                age_days=age_days,
                score=score,
                number=pr.number,
            )
        )
    return items


def _collect_stale_issue_items(
    stats: RepositoryStats,
    repo: TrackedRepository,
    config: BacklogConfig,
    staleness: StalenessConfig,
    now: datetime,
) -> list[BacklogItem]:
    """Create backlog items for stale issues."""
    items: list[BacklogItem] = []
    threshold = float(staleness.issues_days)
    for issue in stats.stale_issue_items:
        if issue.number <= 0:
            continue
        age_days = _days_since(issue.last_activity_at or issue.created_at, now)
        excess = max(0.0, age_days - threshold)
        score = compute_score(
            BacklogCategory.STALE_ISSUE,
            resolve_repo_weight(repo.full_name, config),
            excess,
            reference_days=threshold,
            config=config,
        )
        items.append(
            BacklogItem(
                category=BacklogCategory.STALE_ISSUE,
                repo_full_name=repo.full_name,
                description=f"Issue #{issue.number}: {issue.title}",
                url=issue.url,
                age_days=age_days,
                score=score,
                number=issue.number,
            )
        )
    return items


def _collect_check_items(
    repo: TrackedRepository,
    branches: list[str],
    check_targets: dict[str, set[str]],
    results_by_key: dict[tuple[str, str, str], dict[str, Any]],
    check_defs: list[Any],
    config: BacklogConfig,
    now: datetime,
) -> list[BacklogItem]:
    """Create backlog items for failing checks.

    Check failures use age_factor=1.0 because we don't track when the
    failure first started — only the last run timestamp.
    """
    items: list[BacklogItem] = []
    for check_def in check_defs:
        if not check_def.enabled:
            continue
        applies = repo.full_name in check_targets.get(check_def.slug, set())
        if not applies:
            continue
        for branch in branches:
            key = (check_def.slug, repo.full_name, branch)
            result = results_by_key.get(key)
            if result is None or result["passed"]:
                continue
            # Failing check — flat score (no age escalation)
            category = (
                BacklogCategory.FAILING_CHECK_ERROR
                if check_def.severity == "error"
                else BacklogCategory.FAILING_CHECK_WARNING
            )
            category_weight = _get_category_weight(category, config)
            score = category_weight * resolve_repo_weight(repo.full_name, config)
            items.append(
                BacklogItem(
                    category=category,
                    repo_full_name=repo.full_name,
                    description=f"Check '{check_def.name}' failing on `{branch}`",
                    url="",
                    age_days=0.0,
                    score=score,
                    branch=branch,
                )
            )
    return items


def build_backlog_items(
    cache: dict[str, RepositoryStats],
    repos: dict[str, TrackedRepository],
    config: BacklogConfig,
    staleness: StalenessConfig,
    check_targets: dict[str, set[str]],
    results_by_key: dict[tuple[str, str, str], dict[str, Any]],
    check_defs: list[Any],
    now: datetime | None = None,
) -> list[BacklogItem]:
    """Collect all backlog items from the current cache and sort by score descending."""
    if now is None:
        now = datetime.now(tz=timezone.utc)

    all_items: list[BacklogItem] = []

    for full_name, stats in cache.items():
        repo = repos.get(full_name)
        if repo is None:
            continue

        branches = repo.branches or [stats.default_branch]

        all_items.extend(_collect_workflow_items(stats, repo, config, now))
        all_items.extend(_collect_stale_pr_items(stats, repo, config, staleness, now))
        all_items.extend(_collect_stale_issue_items(stats, repo, config, staleness, now))
        all_items.extend(
            _collect_check_items(
                repo, branches, check_targets, results_by_key, check_defs, config, now
            )
        )

    all_items.sort(key=lambda item: item.score, reverse=True)
    return all_items


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------


def export_markdown(items: list[BacklogItem], title_date: str = "") -> str:
    """Render the full backlog as a Markdown report grouped by priority tier."""
    if not title_date:
        title_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    lines = [f"# Grimoire Backlog — {title_date}", ""]

    # Group by tier
    tier_items: dict[str, list[BacklogItem]] = {}
    for item in items:
        tier_items.setdefault(item.tier, []).append(item)

    tier_order = ["critical", "high", "medium", "low"]
    for tier_name in tier_order:
        tier_list = tier_items.get(tier_name, [])
        if not tier_list:
            continue
        lines.append(
            f"## {tier_name.capitalize()} ({len(tier_list)} item{'s' if len(tier_list) != 1 else ''})"
        )
        lines.append("")
        for item in tier_list:
            lines.append(item.to_markdown())
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Group-by-repository view
# ---------------------------------------------------------------------------


@dataclass
class RepoGroup:
    """A repository's aggregated backlog summary for the grouped view."""

    repo_full_name: str
    items: list[BacklogItem]
    total_score: float = 0.0

    @property
    def tier(self) -> str:
        for threshold, tier_name, _ in PRIORITY_TIERS:
            if self.total_score >= threshold:
                return tier_name
        return "low"

    @property
    def tier_class(self) -> str:
        """DaisyUI badge class for the cumulative priority tier."""
        for threshold, _, cls in PRIORITY_TIERS:
            if self.total_score >= threshold:
                return cls
        return "ghost"

    @property
    def tier_icon(self) -> str:
        """FontAwesome arrow icon for the cumulative priority tier."""
        return TIER_DISPLAY.get(self.tier, TIER_DISPLAY["low"])[0]

    @property
    def tier_color(self) -> str:
        """DaisyUI text color class for the cumulative priority tier."""
        return TIER_DISPLAY.get(self.tier, TIER_DISPLAY["low"])[1]


def group_by_repo(items: list[BacklogItem]) -> list[RepoGroup]:
    """Group backlog items by repository with cumulative scores.

    Returns groups sorted by total_score descending.  Items within each
    group retain their original (score-descending) order.
    """
    buckets: dict[str, list[BacklogItem]] = {}
    for item in items:
        buckets.setdefault(item.repo_full_name, []).append(item)

    groups = [
        RepoGroup(
            repo_full_name=repo,
            items=repo_items,
            total_score=sum(i.score for i in repo_items),
        )
        for repo, repo_items in buckets.items()
    ]
    groups.sort(key=lambda g: g.total_score, reverse=True)
    return groups


# ---------------------------------------------------------------------------
# Group-by-type view
# ---------------------------------------------------------------------------

# Display order and metadata for type groups
TYPE_GROUP_ORDER = [
    ("stale_issues", "Stale Issues", "fa-solid fa-circle-exclamation"),
    ("stale_prs", "Stale PRs", "fa-solid fa-code-pull-request"),
    # Workflow groups are dynamic — inserted here by name
    ("checks", "Checks", "fa-solid fa-clipboard-check"),
    ("others", "Others", "fa-solid fa-ellipsis"),
]


@dataclass
class TypeGroup:
    """A type-based grouping of backlog items."""

    key: str  # e.g. "stale_issues", "workflow:CI", "checks", "others"
    label: str  # e.g. "Stale Issues", "Workflow: CI", "Checks"
    icon: str  # FontAwesome class
    items: list[BacklogItem]
    total_score: float = 0.0

    @property
    def tier(self) -> str:
        for threshold, tier_name, _ in PRIORITY_TIERS:
            if self.total_score >= threshold:
                return tier_name
        return "low"

    @property
    def tier_class(self) -> str:
        """DaisyUI badge class for the cumulative priority tier."""
        for threshold, _, cls in PRIORITY_TIERS:
            if self.total_score >= threshold:
                return cls
        return "ghost"

    @property
    def tier_icon(self) -> str:
        """FontAwesome arrow icon for the cumulative priority tier."""
        return TIER_DISPLAY.get(self.tier, TIER_DISPLAY["low"])[0]

    @property
    def tier_color(self) -> str:
        """DaisyUI text color class for the cumulative priority tier."""
        return TIER_DISPLAY.get(self.tier, TIER_DISPLAY["low"])[1]


def _extract_workflow_name(description: str) -> str:
    """Extract workflow name from a failing workflow description.

    Expected format: "Workflow 'Name' failing on `branch`"
    """
    match = re.match(r"Workflow '([^']+)'", description)
    return match.group(1) if match else "Unknown"


def group_by_type(items: list[BacklogItem]) -> list[TypeGroup]:
    """Group backlog items by type with cumulative scores.

    Groups:
    - stale_issues: all STALE_ISSUE items
    - stale_prs: all STALE_PR items
    - workflow:<name>: one group per unique workflow name (from FAILING_WORKFLOW)
    - checks: all FAILING_CHECK_ERROR and FAILING_CHECK_WARNING items
    - others: any items that don't fit the above categories

    Returns groups in a defined order (stale issues, stale PRs, workflows
    alphabetically, checks, others), with each group sorted by total_score
    descending within its tier. Items within each group retain their
    original (score-descending) order.
    """
    # Buckets for fixed categories
    stale_issues: list[BacklogItem] = []
    stale_prs: list[BacklogItem] = []
    checks: list[BacklogItem] = []
    others: list[BacklogItem] = []
    workflows: dict[str, list[BacklogItem]] = {}

    for item in items:
        if item.category == BacklogCategory.STALE_ISSUE:
            stale_issues.append(item)
        elif item.category == BacklogCategory.STALE_PR:
            stale_prs.append(item)
        elif item.category == BacklogCategory.FAILING_WORKFLOW:
            wf_name = _extract_workflow_name(item.description)
            workflows.setdefault(wf_name, []).append(item)
        elif item.category in (
            BacklogCategory.FAILING_CHECK_ERROR,
            BacklogCategory.FAILING_CHECK_WARNING,
        ):
            checks.append(item)
        else:
            others.append(item)

    groups: list[TypeGroup] = []

    # Stale Issues
    if stale_issues:
        groups.append(
            TypeGroup(
                key="stale_issues",
                label="Stale Issues",
                icon="fa-solid fa-circle-exclamation",
                items=stale_issues,
                total_score=sum(i.score for i in stale_issues),
            )
        )

    # Stale PRs
    if stale_prs:
        groups.append(
            TypeGroup(
                key="stale_prs",
                label="Stale PRs",
                icon="fa-solid fa-code-pull-request",
                items=stale_prs,
                total_score=sum(i.score for i in stale_prs),
            )
        )

    # Workflows — one group per workflow name, sorted alphabetically
    for wf_name in sorted(workflows.keys()):
        wf_items = workflows[wf_name]
        groups.append(
            TypeGroup(
                key=f"workflow:{wf_name}",
                label=f"Workflow: {wf_name}",
                icon="fa-solid fa-gear",
                items=wf_items,
                total_score=sum(i.score for i in wf_items),
            )
        )

    # Checks
    if checks:
        groups.append(
            TypeGroup(
                key="checks",
                label="Checks",
                icon="fa-solid fa-clipboard-check",
                items=checks,
                total_score=sum(i.score for i in checks),
            )
        )

    # Others (catch-all for future categories)
    if others:
        groups.append(
            TypeGroup(
                key="others",
                label="Others",
                icon="fa-solid fa-ellipsis",
                items=others,
                total_score=sum(i.score for i in others),
            )
        )

    return groups
