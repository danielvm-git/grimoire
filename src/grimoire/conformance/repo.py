"""Rules that read files and git history in the repository checkout."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from grimoire.conformance import RuleContext, RuleResult

# Source: danielvm-git/.github scripts/check-conventional-commits.sh
CONVENTIONAL_SUBJECT = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: "
)
COAUTHOR_FOOTER = re.compile(r"^co[- ]authored[- ]by:", re.IGNORECASE | re.MULTILINE)
HISTORY_DEPTH = 50

# README sections every stack template in templates/readmes/ shares.
README_SECTIONS: dict[str, re.Pattern[str]] = {
    "Build status": re.compile(
        r"^#{1,3}[^\w\n]*build status\b", re.IGNORECASE | re.MULTILINE
    ),
    "Tech/framework used": re.compile(
        r"^#{1,3}[^\w\n]*tech\s*/?\s*(stack|framework)", re.IGNORECASE | re.MULTILINE
    ),
    "Contribute": re.compile(r"^#{1,3}[^\w\n]*contribut", re.IGNORECASE | re.MULTILINE),
    "License": re.compile(r"^#{1,3}[^\w\n]*licen[cs]e\b", re.IGNORECASE | re.MULTILINE),
}
ACTIONS_BADGE = re.compile(
    r"!\[[^\]]*\]\([^)]*/actions/workflows/[^)]+/badge\.svg[^)]*\)"
)


def _find_readme(root: Path) -> Path | None:
    for name in ("README.md", "readme.md", "Readme.md"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def agent_context_symlinks(ctx: RuleContext) -> RuleResult:
    """P0: CLAUDE.md and GEMINI.md are symlinks to a real AGENTS.md."""
    root = ctx.repo_path
    problems: list[str] = []
    agents = root / "AGENTS.md"
    if agents.is_symlink() or not agents.is_file():
        problems.append(
            "AGENTS.md must exist as a regular file (the canonical agent context)"
        )
    for name in ("CLAUDE.md", "GEMINI.md"):
        path = root / name
        if not path.is_symlink():
            state = "is a regular file" if path.exists() else "is missing"
            problems.append(f"{name} {state}; it must be a symlink to AGENTS.md")
            continue
        target = os.readlink(path)
        if target not in ("AGENTS.md", "./AGENTS.md"):
            problems.append(f"{name} points to {target!r}; it must point to AGENTS.md")
    return RuleResult.from_problems(problems)


def readme_template(ctx: RuleContext) -> RuleResult:
    """P1: README follows the stack template (badge plus the shared sections)."""
    readme = _find_readme(ctx.repo_path)
    if readme is None:
        return RuleResult.from_problems(["README.md is missing"])
    text = readme.read_text(errors="replace")
    problems = [
        f"missing a '{label}' section"
        for label, pattern in README_SECTIONS.items()
        if not pattern.search(text)
    ]
    if not ACTIONS_BADGE.search(text):
        problems.append("missing a GitHub Actions build status badge")
    return RuleResult.from_problems(problems)


def preflight_documented(ctx: RuleContext) -> RuleResult:
    """P1: README names the single preflight command that gates landing."""
    readme = _find_readme(ctx.repo_path)
    if readme is None:
        return RuleResult.from_problems(["README.md is missing"])
    text = readme.read_text(errors="replace")
    row = re.search(r"^\|\s*\**preflight\**\s*\|", text, re.IGNORECASE | re.MULTILINE)
    heading = re.search(
        r"^#{1,3}[^\w\n]*preflight\b", text, re.IGNORECASE | re.MULTILINE
    )
    if row or heading:
        return RuleResult(passed=True)
    return RuleResult.from_problems(
        ["README has no 'Preflight' row in its Commands table or 'Preflight' section"]
    )


def conventions_md(ctx: RuleContext) -> RuleResult:
    """P1: CONVENTIONS.md exists and documents the Always Green doctrine."""
    path = ctx.repo_path / "CONVENTIONS.md"
    if not path.is_file():
        return RuleResult.from_problems(["CONVENTIONS.md is missing"])
    if not re.search(
        r"always[\s-]+green", path.read_text(errors="replace"), re.IGNORECASE
    ):
        return RuleResult.from_problems(
            ["CONVENTIONS.md does not document the Always Green rule"]
        )
    return RuleResult(passed=True)


def _git_log(root: Path, fmt: str) -> list[str]:
    """Return the last HISTORY_DEPTH non-merge commits of HEAD, NUL-separated by *fmt*."""
    proc = subprocess.run(
        ["git", "log", f"-{HISTORY_DEPTH}", "--no-merges", f"--format={fmt}%x00"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git log failed: {proc.stderr.strip() or proc.returncode}")
    return [entry.strip() for entry in proc.stdout.split("\x00") if entry.strip()]


def conventional_commits(ctx: RuleContext) -> RuleResult:
    """P1: the last 50 non-merge commits use Conventional Commits subjects."""
    entries = _git_log(ctx.repo_path, "%h %s")
    bad = []
    for entry in entries:
        sha, _, subject = entry.partition(" ")
        if not CONVENTIONAL_SUBJECT.match(subject):
            bad.append(f"{sha} {subject}")
    notes = [f"checked {len(entries)} commit(s)"]
    return RuleResult.from_problems([f"not conventional: {b}" for b in bad], notes)


def no_ai_coauthors(ctx: RuleContext) -> RuleResult:
    """P1: no Co-authored-by footers in the last 50 non-merge commits."""
    entries = _git_log(ctx.repo_path, "%h%n%B")
    bad = []
    for entry in entries:
        sha, _, body = entry.partition("\n")
        if COAUTHOR_FOOTER.search(body):
            bad.append(sha)
    notes = [f"checked {len(entries)} commit(s)"]
    return RuleResult.from_problems(
        [f"{sha} has a Co-authored-by footer" for sha in bad], notes
    )
