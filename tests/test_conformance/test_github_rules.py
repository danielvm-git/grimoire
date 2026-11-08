"""Branch protection rules against mocked GitHub API responses (respx)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from grimoire.conformance import RuleContext
from grimoire.conformance import github as gr

API = "https://api.github.com/repos/danielvm-git/app"
CLASSIC = f"{API}/branches/main/protection"
RULES = f"{API}/rules/branches/main"


def _ctx(tmp_path: Path, token: str = "t") -> RuleContext:
    return RuleContext(
        repo_path=tmp_path,
        repo_full_name="danielvm-git/app",
        default_branch="main",
        token=token,
    )


def _classic(
    force: bool = False, deletion: bool = False, approvals: int | None = 1
) -> dict:
    body: dict = {
        "allow_force_pushes": {"enabled": force},
        "allow_deletions": {"enabled": deletion},
    }
    if approvals is not None:
        body["required_pull_request_reviews"] = {
            "required_approving_review_count": approvals
        }
    return body


@respx.mock
def test_classic_protection_passes(tmp_path: Path) -> None:
    respx.get(CLASSIC).mock(return_value=httpx.Response(200, json=_classic()))
    respx.get(RULES).mock(return_value=httpx.Response(200, json=[]))
    assert gr.branch_protection(_ctx(tmp_path)).passed
    assert gr.pr_required(_ctx(tmp_path)).passed


@respx.mock
def test_unprotected_branch_fails(tmp_path: Path) -> None:
    respx.get(CLASSIC).mock(
        return_value=httpx.Response(404, json={"message": "Branch not protected"})
    )
    respx.get(RULES).mock(return_value=httpx.Response(200, json=[]))
    result = gr.branch_protection(_ctx(tmp_path))
    assert not result.passed
    assert result.problems == ["'main' is not protected"]
    assert not gr.pr_required(_ctx(tmp_path)).passed


@respx.mock
def test_force_push_allowed_fails(tmp_path: Path) -> None:
    respx.get(CLASSIC).mock(return_value=httpx.Response(200, json=_classic(force=True)))
    respx.get(RULES).mock(return_value=httpx.Response(200, json=[]))
    assert gr.branch_protection(_ctx(tmp_path)).problems == [
        "'main' allows force-pushes"
    ]


@respx.mock
def test_deletion_allowed_fails(tmp_path: Path) -> None:
    respx.get(CLASSIC).mock(
        return_value=httpx.Response(200, json=_classic(deletion=True))
    )
    respx.get(RULES).mock(return_value=httpx.Response(200, json=[]))
    assert gr.branch_protection(_ctx(tmp_path)).problems == ["'main' allows deletion"]


@respx.mock
def test_rulesets_satisfy_protection(tmp_path: Path) -> None:
    respx.get(CLASSIC).mock(return_value=httpx.Response(404))
    respx.get(RULES).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"type": "non_fast_forward"},
                {"type": "deletion"},
                {
                    "type": "pull_request",
                    "parameters": {"required_approving_review_count": 1},
                },
            ],
        )
    )
    assert gr.branch_protection(_ctx(tmp_path)).passed
    assert gr.pr_required(_ctx(tmp_path)).passed


@respx.mock
def test_pr_without_approval_fails(tmp_path: Path) -> None:
    respx.get(CLASSIC).mock(
        return_value=httpx.Response(200, json=_classic(approvals=0))
    )
    respx.get(RULES).mock(return_value=httpx.Response(200, json=[]))
    result = gr.pr_required(_ctx(tmp_path))
    assert not result.passed
    assert "no approving review" in result.problems[0]


@respx.mock
def test_unreadable_api_fails_not_passes(tmp_path: Path) -> None:
    respx.get(CLASSIC).mock(
        return_value=httpx.Response(403, json={"message": "Upgrade to Pro"})
    )
    respx.get(RULES).mock(return_value=httpx.Response(403))
    result = gr.branch_protection(_ctx(tmp_path))
    assert not result.passed
    assert "cannot verify" in result.problems[0]
    assert not gr.pr_required(_ctx(tmp_path)).passed


def test_missing_token_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="GH_TOKEN"):
        gr.branch_protection(_ctx(tmp_path, token=""))
