"""Rules that read repository settings from the GitHub API.

Protection can come from classic branch protection or from repository rulesets,
so both endpoints are read and either one may satisfy a rule. A rule fails when
neither endpoint can be read — it never passes on something it could not see.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from grimoire.conformance import RuleContext, RuleResult


@dataclass
class Protection:
    classic: dict[str, Any] | None  # classic protection body when HTTP 200
    classic_status: int
    rules: list[dict[str, Any]] | None  # active ruleset rules when HTTP 200
    rules_status: int

    @property
    def rule_types(self) -> set[str]:
        return {str(r.get("type")) for r in self.rules or []}

    @property
    def readable(self) -> bool:
        return self.classic_status in (200, 404) or self.rules is not None


def _get(client: httpx.Client, url: str) -> tuple[int, Any]:
    try:
        resp = client.get(url)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc}") from exc
    body = resp.json() if resp.status_code == 200 else None
    return resp.status_code, body


def fetch_protection(ctx: RuleContext) -> Protection:
    if not ctx.repo_full_name or "/" not in ctx.repo_full_name:
        raise RuntimeError("REPO_FULL_NAME is not set")
    if not ctx.token:
        raise RuntimeError("GH_TOKEN is not set; cannot read branch protection")
    base = f"{ctx.api_url.rstrip('/')}/repos/{ctx.repo_full_name}"
    headers = {
        "Authorization": f"Bearer {ctx.token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(headers=headers, timeout=20) as client:
        classic_status, classic = _get(
            client, f"{base}/branches/{ctx.default_branch}/protection"
        )
        rules_status, rules = _get(
            client, f"{base}/rules/branches/{ctx.default_branch}"
        )
    return Protection(
        classic=classic if isinstance(classic, dict) else None,
        classic_status=classic_status,
        rules=rules if isinstance(rules, list) else None,
        rules_status=rules_status,
    )


def _enabled(body: dict[str, Any] | None, key: str) -> bool | None:
    if body is None:
        return None
    value = body.get(key)
    return bool(value.get("enabled")) if isinstance(value, dict) else False


def _unreadable(p: Protection, branch: str) -> RuleResult:
    return RuleResult.from_problems(
        [
            f"cannot verify protection on '{branch}' "
            f"(protection API HTTP {p.classic_status}, rulesets API HTTP {p.rules_status}); "
            "check the token's administration read permission or the repo plan"
        ]
    )


def branch_protection(ctx: RuleContext) -> RuleResult:
    """P0: the default branch blocks force-pushes and deletion."""
    p = fetch_protection(ctx)
    if not p.readable:
        return _unreadable(p, ctx.default_branch)
    force_allowed = _enabled(p.classic, "allow_force_pushes")
    deletion_allowed = _enabled(p.classic, "allow_deletions")
    force_blocked = force_allowed is False or "non_fast_forward" in p.rule_types
    deletion_blocked = deletion_allowed is False or "deletion" in p.rule_types
    if p.classic is None and not p.rule_types:
        return RuleResult.from_problems([f"'{ctx.default_branch}' is not protected"])
    problems = []
    if not force_blocked:
        problems.append(f"'{ctx.default_branch}' allows force-pushes")
    if not deletion_blocked:
        problems.append(f"'{ctx.default_branch}' allows deletion")
    return RuleResult.from_problems(problems)


def pr_required(ctx: RuleContext) -> RuleResult:
    """P1: the default branch is protected.

    Solo-owner policy: direct push is allowed, so neither a pull request nor an
    approving review is required. Only an unprotected or unreadable branch fails.
    """
    p = fetch_protection(ctx)
    if not p.readable:
        return _unreadable(p, ctx.default_branch)
    if p.classic is None and not p.rules:
        return RuleResult.from_problems([f"'{ctx.default_branch}' is not protected"])
    return RuleResult(passed=True, notes=["direct push allowed (solo-owner policy)"])
