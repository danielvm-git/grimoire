"""Build copy-pasteable agent prompts for a repository's pending problems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grimoire.models import RepositoryStats

MAX_OUTPUT_CHARS = 2000

_CONVENTIONS = (
    "Make the smallest change that resolves this. Run the project's tests/linters "
    "before finishing, commit using Conventional Commits, and open a pull request."
)


@dataclass
class Pendency:
    """One thing that is wrong with a repo, plus the prompt that fixes it."""

    kind: str  # "check" | "workflow" | "issue" | "pr"
    severity: str  # "error" | "warning"
    title: str
    branch: str
    prompt: str


def _truncate(output: str) -> str:
    output = output.strip()
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    return "[...truncated...]\n" + output[-MAX_OUTPUT_CHARS:]


def _header(full_name: str, branch: str) -> str:
    return f"Repository: {full_name} (https://github.com/{full_name})\nBranch: {branch}"


def build_check_prompt(
    full_name: str,
    branch: str,
    check_name: str,
    description: str,
    output: str,
) -> str:
    """Prompt for a failing Grimoire check."""
    lines = [
        _header(full_name, branch),
        "",
        f'Problem: the Grimoire check "{check_name}" is failing.',
    ]
    if description:
        lines.append(f"What the check verifies: {description.strip()}")
    lines += [
        "",
        "Output of the failing check:",
        "```",
        _truncate(output) or "(no output)",
        "```",
        "",
        "Task: investigate the root cause in this repository and fix it so the "
        "check passes. " + _CONVENTIONS,
    ]
    return "\n".join(lines)


def build_workflow_prompt(
    full_name: str, branch: str, workflow: str, run_url: str
) -> str:
    """Prompt for a failing GitHub Actions workflow."""
    lines = [
        _header(full_name, branch),
        "",
        f'Problem: the GitHub Actions workflow "{workflow}" is failing.',
    ]
    if run_url:
        lines.append(f"Failing run: {run_url}")
    lines += [
        "",
        "Task: read the logs of the failing run "
        f"(e.g. `gh run view --repo {full_name} --log-failed`), find the root "
        "cause, and fix it so the workflow passes. " + _CONVENTIONS,
    ]
    return "\n".join(lines)


def build_stale_prompt(
    full_name: str, branch: str, kind: str, number: int, title: str, url: str
) -> str:
    """Prompt for a stale issue or pull request."""
    label = "issue" if kind == "issue" else "pull request"
    show = "issue" if kind == "issue" else "pr"
    if kind == "issue":
        task = (
            "Task: read the issue and its comments. If it is already resolved, "
            "close it with an explanation; if it is still valid, fix it or reply "
            "with a concrete next step."
        )
    else:
        task = (
            "Task: read the pull request and its review comments. Bring it up to "
            "date with the base branch, address outstanding feedback, and get CI "
            "green; if it is obsolete, close it with an explanation."
        )
    return "\n".join(
        [
            _header(full_name, branch),
            "",
            f'Problem: {label} #{number} "{title}" is stale (no recent activity).',
            f"Link: {url}",
            f"(`gh {show} view {number} --repo {full_name} --comments`)",
            "",
            task,
        ]
    )


def build_pendencies(
    full_name: str,
    stats: RepositoryStats,
    checks_by_branch: dict[str, list[dict[str, Any]]],
    check_descriptions: dict[str, str],
    check_outputs: dict[int, str],
) -> list[Pendency]:
    """Collect everything wrong with a repo, each with its own prompt."""
    items: list[Pendency] = []

    for branch, checks in checks_by_branch.items():
        for chk in checks:
            if chk["status"] != "fail":
                continue
            items.append(
                Pendency(
                    kind="check",
                    severity=chk.get("severity", "error"),
                    title=f"Check: {chk['check_name']}",
                    branch=branch,
                    prompt=build_check_prompt(
                        full_name,
                        branch,
                        chk["check_name"],
                        check_descriptions.get(chk["check_slug"], ""),
                        check_outputs.get(chk.get("id") or -1, ""),
                    ),
                )
            )

    for wf in stats.workflows:
        if wf.status != "failure":
            continue
        items.append(
            Pendency(
                kind="workflow",
                severity="error",
                title=f"Workflow: {wf.name}",
                branch=wf.branch,
                prompt=build_workflow_prompt(
                    full_name, wf.branch, wf.name, wf.run_url or wf.url
                ),
            )
        )

    for issue in stats.stale_issue_items:
        items.append(
            Pendency(
                kind="issue",
                severity="warning",
                title=f"Stale issue #{issue.number}: {issue.title}",
                branch=stats.default_branch,
                prompt=build_stale_prompt(
                    full_name,
                    stats.default_branch,
                    "issue",
                    issue.number,
                    issue.title,
                    issue.url,
                ),
            )
        )

    for pr in stats.stale_pr_items:
        items.append(
            Pendency(
                kind="pr",
                severity="warning",
                title=f"Stale PR #{pr.number}: {pr.title}",
                branch=stats.default_branch,
                prompt=build_stale_prompt(
                    full_name, stats.default_branch, "pr", pr.number, pr.title, pr.url
                ),
            )
        )

    return items


def build_repo_prompt(full_name: str, pendencies: list[Pendency]) -> str:
    """Combine every pendency into one prompt for a single agent session."""
    if not pendencies:
        return ""
    lines = [
        f"Repository: {full_name} (https://github.com/{full_name})",
        "",
        f"This repository has {len(pendencies)} pending problem(s). Resolve them "
        "one at a time, most severe first, with a separate commit per problem.",
    ]
    ordered = sorted(pendencies, key=lambda p: p.severity != "error")
    for i, p in enumerate(ordered, 1):
        lines += ["", f"## {i}. {p.title} [{p.severity}, branch {p.branch}]", ""]
        # drop the per-item header; the repo is already stated above
        body = p.prompt.split("\n\n", 1)[1] if "\n\n" in p.prompt else p.prompt
        lines.append(body)
    return "\n".join(lines)
