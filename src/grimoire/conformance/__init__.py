"""Conformance rules: checks that a repo follows the danielvm-git/.github patterns.

Each rule inspects a checked-out repository (and, for some rules, the GitHub API)
and returns a :class:`RuleResult`. Rules never pass on something they could not
verify — an unreadable file or an API error is a failure with a reason.

Run one rule from a check script with ``python -m grimoire.conformance <rule>``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RuleContext:
    """Inputs a rule may use. Built from the check environment by the CLI."""

    repo_path: Path
    repo_full_name: str = ""
    default_branch: str = "main"
    token: str = ""
    api_url: str = "https://api.github.com"


@dataclass
class RuleResult:
    passed: bool
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_problems(
        cls, problems: list[str], notes: list[str] | None = None
    ) -> RuleResult:
        return cls(passed=not problems, problems=problems, notes=notes or [])


Rule = Callable[[RuleContext], RuleResult]


def get_rules() -> dict[str, Rule]:
    """Return every rule keyed by its slug (the check filename uses the same slug)."""
    from grimoire.conformance import github, repo, workflows

    return {
        # P0
        "agent-context-symlinks": repo.agent_context_symlinks,
        "ci-layout": workflows.ci_layout,
        "ci-workflow-permissions": workflows.ci_workflow_permissions,
        "ci-job-timeouts": workflows.ci_job_timeouts,
        "ci-concurrency": workflows.ci_concurrency,
        "ci-runner-pinned": workflows.ci_runner_pinned,
        "ci-actions-pinned": workflows.ci_actions_pinned,
        "branch-protection": github.branch_protection,
        "bigbase-deploy": workflows.bigbase_deploy,
        # P1
        "readme-template": repo.readme_template,
        "preflight-documented": repo.preflight_documented,
        "conventions-md": repo.conventions_md,
        "conventional-commits": repo.conventional_commits,
        "no-ai-coauthors": repo.no_ai_coauthors,
        "pr-required": github.pr_required,
    }
