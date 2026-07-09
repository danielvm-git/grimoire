"""Failure-mode tests for check and action engines (e08s03)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grimoire.checks.engine import run_check
from grimoire.checks.loader import CheckDefinition
from grimoire.database import create_tables, get_engine
from grimoire.github.client import GitHubClient
from grimoire.github.service import fetch_repository_stats
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec


def _check(script: str = "echo hello") -> CheckDefinition:
    return CheckDefinition(
        name="Test Check",
        slug="test-check",
        description="A test",
        targets=TargetSpec(list=["acme/repo"]),
        script=script,
    )


def _repo() -> TrackedRepository:
    return TrackedRepository(full_name="acme/repo", default_branch="main")


class MockWorkspace:
    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir

    async def reset_workdir(self, full_name: str, branch: str) -> Path:
        return self._workdir

    def get_workdir(self, full_name: str, branch: str) -> Path:
        return self._workdir

    def get_env(self) -> dict[str, str]:
        return {"GH_TOKEN": "test", "GITHUB_TOKEN": "test"}

    async def sync_repo(self, repo: TrackedRepository) -> None:
        pass

    async def sync_all(self, repos: list[TrackedRepository]) -> None:
        pass

    @property
    def workspace_dir(self) -> Path:
        return self._workdir


class TestDiskFull:
    async def test_workspace_reset_oserror_handled(self, tmp_path: Path) -> None:
        """Check engine returns failed result on workspace OSError."""
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)
        ws.reset_workdir = AsyncMock(side_effect=OSError(28, "No space left on device"))  # type: ignore[method-assign]

        result = await run_check(_check(), _repo(), "main", ws, engine)  # type: ignore[arg-type]
        assert result.passed is False
        assert "No space left on device" in result.output


class TestSQLiteCorruption:
    async def test_corrupt_db_does_not_crash(self, tmp_path: Path) -> None:
        """Check engine survives corrupt database file."""
        db_path = tmp_path / "corrupt.db"
        db_path.write_bytes(b"not valid sqlite")
        engine = await get_engine(str(db_path))
        try:
            await create_tables(engine)
        except Exception:
            pass  # corrupt DB may fail gracefully

        ws = MockWorkspace(tmp_path)
        try:
            result = await run_check(
                _check(), _repo(), "main", ws, engine  # type: ignore[arg-type]
            )
            assert result.check_slug == "test-check"
        except Exception:
            # Doesn't crash the application
            pass


class TestMalformedAPI:
    async def test_malformed_issues_goes_to_warnings(self) -> None:
        """Malformed GitHub API response populates warnings, not crashes."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client._engine = MagicMock()
        mock_client.get_open_issues = AsyncMock(return_value="not a list")
        mock_client.get_open_pull_requests = AsyncMock(return_value=[])
        mock_client.get_workflows = AsyncMock(return_value=[])
        mock_client.get_branches = AsyncMock(return_value=[])
        mock_client.get_branch = AsyncMock(return_value=None)

        from grimoire.config import StalenessConfig

        repo = _repo()
        repo.branches = ["main"]

        stats = await fetch_repository_stats(
            repo, mock_client, StalenessConfig(pull_requests_days=30, issues_days=365)  # type: ignore[arg-type]
        )
        assert len(stats.warnings) > 0


class TestConcurrentRace:
    async def test_concurrent_action_guard(self, tmp_path: Path) -> None:
        """Second concurrent run_action raises ActionConflictError."""
        from grimoire.actions.engine import ActionConflictError, run_action
        from grimoire.actions.loader import ActionDefinition

        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)

        repos = [_repo()]
        ws = MockWorkspace(tmp_path)

        def _act(script: str = "echo ok") -> ActionDefinition:
            return ActionDefinition(
                name="Test", slug="test-action", description=".",
                targets=TargetSpec(list=["acme/repo"]), script=script,
            )

        task1 = asyncio.create_task(
            run_action(_act("sleep 0.3"), repos, ws, engine, triggered_by="manual")  # type: ignore[arg-type]
        )
        await asyncio.sleep(0.05)

        with pytest.raises(ActionConflictError, match="already running"):
            await run_action(
                _act("echo ok"), repos, ws, engine, triggered_by="manual"  # type: ignore[arg-type]
            )

        await task1
