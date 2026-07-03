"""Tests for TargetSpec validation and resolve_targets."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec, resolve_targets, target_env

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockWorkspace:
    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir

    async def reset_workdir(self, full_name: str, branch: str) -> Path:
        return self._workdir

    def get_workdir(self, full_name: str, branch: str) -> Path:
        return self._workdir

    def get_env(self) -> dict[str, str]:
        return {"GH_TOKEN": "test", "GITHUB_TOKEN": "test"}


def _repos() -> list[TrackedRepository]:
    return [
        TrackedRepository(full_name="acme/alpha", default_branch="main"),
        TrackedRepository(
            full_name="acme/beta", default_branch="main", branches=["main", "develop"]
        ),
        TrackedRepository(full_name="other/gamma", default_branch="develop"),
    ]


# ---------------------------------------------------------------------------
# TargetSpec validation
# ---------------------------------------------------------------------------


class TestTargetSpecValidation:
    def test_exactly_one_list(self) -> None:
        ts = TargetSpec(list=["acme/alpha"])
        assert ts.list == ["acme/alpha"]

    def test_exactly_one_regex(self) -> None:
        ts = TargetSpec(regex="acme/.*")
        assert ts.regex == "acme/.*"

    def test_exactly_one_script(self) -> None:
        ts = TargetSpec(script="exit 0")
        assert ts.script == "exit 0"

    def test_none_set_raises(self) -> None:
        with pytest.raises(ValidationError, match="Exactly one"):
            TargetSpec()

    def test_two_set_raises(self) -> None:
        with pytest.raises(ValidationError, match="Exactly one"):
            TargetSpec(list=["a"], regex="b")

    def test_all_set_raises(self) -> None:
        with pytest.raises(ValidationError, match="Exactly one"):
            TargetSpec(list=["a"], regex="b", script="c")


# ---------------------------------------------------------------------------
# resolve_targets
# ---------------------------------------------------------------------------


class TestResolveTargetsList:
    async def test_list_match_expands_to_all_observed_branches(self, tmp_path: Path) -> None:
        ws = MockWorkspace(tmp_path)
        spec = TargetSpec(list=["acme/alpha", "acme/beta"])
        result = await resolve_targets(spec, _repos(), ws)  # type: ignore[arg-type]
        by_name = {r.full_name: branches for r, branches in result}
        assert by_name == {
            "acme/alpha": ["main"],
            "acme/beta": ["main", "develop"],
        }

    async def test_list_no_match(self, tmp_path: Path) -> None:
        ws = MockWorkspace(tmp_path)
        spec = TargetSpec(list=["nonexistent/repo"])
        result = await resolve_targets(spec, _repos(), ws)  # type: ignore[arg-type]
        assert result == []


class TestResolveTargetsRegex:
    async def test_regex_match_expands_to_all_observed_branches(self, tmp_path: Path) -> None:
        ws = MockWorkspace(tmp_path)
        spec = TargetSpec(regex="acme/.*")
        result = await resolve_targets(spec, _repos(), ws)  # type: ignore[arg-type]
        by_name = {r.full_name: branches for r, branches in result}
        assert by_name == {
            "acme/alpha": ["main"],
            "acme/beta": ["main", "develop"],
        }

    async def test_regex_no_match(self, tmp_path: Path) -> None:
        ws = MockWorkspace(tmp_path)
        spec = TargetSpec(regex="^zzz/")
        result = await resolve_targets(spec, _repos(), ws)  # type: ignore[arg-type]
        assert result == []


class TestResolveTargetsScript:
    async def test_script_include_all_branches(self, tmp_path: Path) -> None:
        ws = MockWorkspace(tmp_path)
        spec = TargetSpec(script="exit 0")
        repos = [TrackedRepository(full_name="acme/beta", branches=["main", "develop"])]
        result = await resolve_targets(spec, repos, ws)  # type: ignore[arg-type]
        assert len(result) == 1
        repo, branches = result[0]
        assert repo.full_name == "acme/beta"
        assert branches == ["main", "develop"]

    async def test_script_exclude_all_branches_drops_repo(self, tmp_path: Path) -> None:
        ws = MockWorkspace(tmp_path)
        spec = TargetSpec(script="exit 1")
        repos = [TrackedRepository(full_name="acme/alpha", default_branch="main")]
        result = await resolve_targets(spec, repos, ws)  # type: ignore[arg-type]
        assert result == []

    async def test_script_can_filter_by_branch(self, tmp_path: Path) -> None:
        """Script targeting evaluates per branch — enables 'default branch only' patterns."""
        ws = MockWorkspace(tmp_path)
        spec = TargetSpec(script='[ "$BRANCH" = "$DEFAULT_BRANCH" ]')
        repos = [
            TrackedRepository(
                full_name="acme/beta", default_branch="main", branches=["main", "develop"]
            ),
        ]
        result = await resolve_targets(spec, repos, ws)  # type: ignore[arg-type]
        assert len(result) == 1
        _, branches = result[0]
        assert branches == ["main"]


# ---------------------------------------------------------------------------
# target_env
# ---------------------------------------------------------------------------


class TestTargetEnv:
    def test_populates_repo_and_branch_vars(self, tmp_path: Path) -> None:
        ws = MockWorkspace(tmp_path)
        repo = TrackedRepository(
            full_name="acme/alpha", default_branch="main", branches=["main", "develop"]
        )
        env = target_env(ws, repo, "develop")  # type: ignore[arg-type]
        assert env["REPO_OWNER"] == "acme"
        assert env["REPO_NAME"] == "alpha"
        assert env["REPO_FULL_NAME"] == "acme/alpha"
        assert env["BRANCH"] == "develop"
        assert env["DEFAULT_BRANCH"] == "main"
        # Workspace env passthrough
        assert env["GH_TOKEN"] == "test"
