"""Tests for publishing check results as GitHub commit statuses."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import pytest
import respx

from grimoire.checks.engine import run_check
from grimoire.checks.loader import CheckDefinition
from grimoire.checks.status import publish_commit_status
from grimoire.database import create_tables, get_engine
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec

SHA = "a" * 40
URL = f"https://api.github.com/repos/acme/repo/statuses/{SHA}"


class TestPublishCommitStatus:
    @respx.mock
    async def test_posts_state_context_description(self) -> None:
        route = respx.post(URL).mock(return_value=httpx.Response(201, json={}))
        ok = await publish_commit_status(
            "tok", "acme/repo", SHA, passed=False, context="grimoire/audit", detail="x"
        )
        assert ok is True
        req = route.calls.last.request
        assert req.headers["Authorization"] == "Bearer tok"
        body = json.loads(req.content)
        assert body["state"] == "failure"
        assert body["context"] == "grimoire/audit"
        assert "x" in body["description"]

    @respx.mock
    async def test_success_state(self) -> None:
        route = respx.post(URL).mock(return_value=httpx.Response(201, json={}))
        await publish_commit_status(
            "tok", "acme/repo", SHA, passed=True, context="c", detail=""
        )
        assert json.loads(route.calls.last.request.content)["state"] == "success"

    @respx.mock
    async def test_description_truncated_to_140(self) -> None:
        route = respx.post(URL).mock(return_value=httpx.Response(201, json={}))
        await publish_commit_status(
            "tok", "acme/repo", SHA, passed=False, context="c", detail="y" * 500
        )
        desc = json.loads(route.calls.last.request.content)["description"]
        assert len(desc) <= 140

    @respx.mock
    @pytest.mark.parametrize("status", [403, 404, 422, 500])
    async def test_http_errors_return_false(self, status: int) -> None:
        respx.post(URL).mock(return_value=httpx.Response(status, json={}))
        ok = await publish_commit_status(
            "tok", "acme/repo", SHA, passed=True, context="c", detail=""
        )
        assert ok is False

    @respx.mock
    async def test_network_error_returns_false(self) -> None:
        respx.post(URL).mock(side_effect=httpx.ConnectError("down"))
        ok = await publish_commit_status(
            "tok", "acme/repo", SHA, passed=True, context="c", detail=""
        )
        assert ok is False


class _Workspace:
    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir

    async def reset_workdir(self, full_name: str, branch: str) -> Path:
        return self._workdir

    def get_env(self) -> dict[str, str]:
        return {"GH_TOKEN": "tok", "GITHUB_TOKEN": "tok"}


def _git_repo(path: Path) -> str:
    def git(*a: str) -> str:
        return subprocess.run(
            ["git", *a], cwd=path, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q")
    git(
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "x",
    )
    return git("rev-parse", "HEAD")


def _check(script: str, publish: str | None) -> CheckDefinition:
    return CheckDefinition(
        name="Audit",
        slug="audit",
        description="d",
        targets=TargetSpec(list=["acme/repo"]),
        script=script,
        publish_status=publish,
    )


_REPO = TrackedRepository(full_name="acme/repo", default_branch="main")


class TestEnginePublishes:
    @respx.mock
    async def test_publishes_when_configured(self, tmp_path: Path) -> None:
        sha = _git_repo(tmp_path)
        route = respx.post(
            f"https://api.github.com/repos/acme/repo/statuses/{sha}"
        ).mock(return_value=httpx.Response(201, json={}))
        engine = await get_engine(str(tmp_path / "t.db"))
        await create_tables(engine)
        result = await run_check(
            _check("exit 1", "grimoire/audit"),
            _REPO,
            "main",
            _Workspace(tmp_path),  # type: ignore[arg-type]
            engine,
        )
        assert result.passed is False
        assert route.call_count == 1
        body = json.loads(route.calls.last.request.content)
        assert body["state"] == "failure"
        assert body["context"] == "grimoire/audit"

    @respx.mock
    async def test_no_call_when_not_configured(self, tmp_path: Path) -> None:
        _git_repo(tmp_path)
        engine = await get_engine(str(tmp_path / "t.db"))
        await create_tables(engine)
        await run_check(
            _check("exit 0", None),
            _REPO,
            "main",
            _Workspace(tmp_path),  # type: ignore[arg-type]
            engine,
        )
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_publish_failure_does_not_fail_check(self, tmp_path: Path) -> None:
        sha = _git_repo(tmp_path)
        respx.post(f"https://api.github.com/repos/acme/repo/statuses/{sha}").mock(
            return_value=httpx.Response(403, json={})
        )
        engine = await get_engine(str(tmp_path / "t.db"))
        await create_tables(engine)
        result = await run_check(
            _check("exit 0", "grimoire/audit"),
            _REPO,
            "main",
            _Workspace(tmp_path),  # type: ignore[arg-type]
            engine,
        )
        assert result.passed is True

    @respx.mock
    async def test_not_a_git_workdir_is_skipped(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "t.db"))
        await create_tables(engine)
        result = await run_check(
            _check("exit 0", "grimoire/audit"),
            _REPO,
            "main",
            _Workspace(tmp_path),  # type: ignore[arg-type]
            engine,
        )
        assert result.passed is True
        assert respx.calls.call_count == 0
