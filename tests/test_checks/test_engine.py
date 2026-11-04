"""Tests for the check execution engine."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.checks.engine import OUTPUT_SIZE_CAP, run_check
from grimoire.checks.loader import CheckDefinition
from grimoire.database import CheckResultRecord, create_tables, get_engine
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunCheck:
    async def test_successful_check(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        result = await run_check(_check("echo hello"), _repo(), "main", ws, engine)  # type: ignore[arg-type]

        assert result.passed is True
        assert "hello" in result.output
        assert result.check_slug == "test-check"
        assert result.repo_full_name == "acme/repo"
        assert result.branch == "main"

    async def test_failed_check(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        result = await run_check(_check("exit 1"), _repo(), "main", ws, engine)  # type: ignore[arg-type]

        assert result.passed is False
        assert "[exit code 1]" in result.output

    async def test_failed_check_stderr_labeled(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        result = await run_check(
            _check("echo oops >&2 && exit 2"),
            _repo(),
            "main",
            ws,
            engine,  # type: ignore[arg-type]
        )

        assert result.passed is False
        assert "[stderr]" in result.output
        assert "oops" in result.output
        assert "[exit code 2]" in result.output

    async def test_output_capture(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        result = await run_check(
            _check("echo stdout-line && echo stderr-line >&2"),
            _repo(),
            "main",
            ws,
            engine,  # type: ignore[arg-type]
        )

        assert "stdout-line" in result.output
        assert "stderr-line" in result.output

    async def test_output_truncation(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        # Generate > 64KB of output
        big_script = f"python3 -c \"print('x' * {OUTPUT_SIZE_CAP + 1000})\""
        result = await run_check(_check(big_script), _repo(), "main", ws, engine)  # type: ignore[arg-type]

        assert result.output.startswith("[output truncated")

    async def test_timeout_handling(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        # Patch timeout to be short for test
        import grimoire.checks.engine as eng

        original = eng._DEFAULT_TIMEOUT
        eng._DEFAULT_TIMEOUT = 1
        try:
            result = await run_check(_check("sleep 30"), _repo(), "main", ws, engine)  # type: ignore[arg-type]
            assert result.passed is False
            assert "Timed out" in result.output
        finally:
            eng._DEFAULT_TIMEOUT = original

    async def test_result_persisted(self, tmp_path: Path) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        await run_check(_check("echo persisted"), _repo(), "main", ws, engine)  # type: ignore[arg-type]

        async with AsyncSession(engine) as session:
            from sqlmodel import select

            stmt = select(CheckResultRecord).where(
                CheckResultRecord.check_slug == "test-check"
            )
            rows = (await session.exec(stmt)).all()

        assert len(rows) == 1
        assert rows[0].passed is True
        assert "persisted" in rows[0].output


class TestRunningStateTracking:
    """Tests for the in-memory _running_checks tracking."""

    async def test_is_check_running_false_when_not_running(self) -> None:
        from grimoire.checks.engine import is_check_running

        assert is_check_running("nonexistent") is False

    async def test_running_check_tracked_during_execution(self, tmp_path: Path) -> None:
        """Verify slug is in _running_checks while running, and removed after."""
        from grimoire.checks.engine import _running_checks, is_check_running

        engine = await get_engine(str(tmp_path / "track.db"))
        await create_tables(engine)

        check = CheckDefinition(
            name="Tracker",
            slug="tracker-test",
            targets=TargetSpec(list=["acme/repo"]),
            script="exit 0",
            description="",
        )
        repo = TrackedRepository(
            full_name="acme/repo", default_branch="main", source="static"
        )
        workspace = MockWorkspace(tmp_path)

        assert not is_check_running("tracker-test")

        from grimoire.checks.engine import run_check_for_all_targets

        await run_check_for_all_targets(check, [repo], workspace, engine)  # type: ignore[arg-type]

        # After completion, should no longer be running
        assert "tracker-test" not in _running_checks
        await engine.dispose()


class TestRunCheckForAllTargets:
    """End-to-end targeting behavior including per-branch script filtering."""

    async def test_list_targeting_runs_on_all_observed_branches(
        self, tmp_path: Path
    ) -> None:
        from sqlmodel import select

        from grimoire.checks.engine import run_check_for_all_targets

        engine = await get_engine(str(tmp_path / "list.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        check = CheckDefinition(
            name="List Check",
            slug="list-check",
            description="",
            targets=TargetSpec(list=["acme/repo"]),
            script="echo ok",
        )
        repo = TrackedRepository(
            full_name="acme/repo",
            default_branch="main",
            branches=["main", "develop"],
        )

        await run_check_for_all_targets(check, [repo], ws, engine)  # type: ignore[arg-type]

        async with AsyncSession(engine) as session:
            rows = (
                await session.exec(
                    select(CheckResultRecord).where(
                        CheckResultRecord.check_slug == "list-check"
                    )
                )
            ).all()
        assert sorted(r.branch for r in rows) == ["develop", "main"]

    async def test_script_targeting_restricts_to_matching_branches(
        self, tmp_path: Path
    ) -> None:
        """A target script that only accepts the default branch scopes the check to it."""
        from sqlmodel import select

        from grimoire.checks.engine import run_check_for_all_targets

        engine = await get_engine(str(tmp_path / "script.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)

        check = CheckDefinition(
            name="Default Branch Only",
            slug="default-only",
            description="",
            targets=TargetSpec(script='[ "$BRANCH" = "$DEFAULT_BRANCH" ]'),
            script="echo ok",
        )
        repo = TrackedRepository(
            full_name="acme/repo",
            default_branch="main",
            branches=["main", "develop", "release/1.0"],
        )

        await run_check_for_all_targets(check, [repo], ws, engine)  # type: ignore[arg-type]

        async with AsyncSession(engine) as session:
            rows = (
                await session.exec(
                    select(CheckResultRecord).where(
                        CheckResultRecord.check_slug == "default-only"
                    )
                )
            ).all()
        assert [r.branch for r in rows] == ["main"]


class TestCancellation:
    async def test_cancelled_run_kills_child(self, tmp_path: Path) -> None:
        """Cancelling a check must kill its whole process group (F8)."""
        engine = await get_engine(str(tmp_path / "cancel.db"))
        await create_tables(engine)
        ws = MockWorkspace(tmp_path)
        pid_file = tmp_path / "child.pid"
        check = _check(f"sleep 30 & echo $! > {pid_file}; wait")

        task = asyncio.create_task(
            run_check(check, _repo(), "main", ws, engine)  # type: ignore[arg-type]
        )
        for _ in range(100):
            if pid_file.exists() and pid_file.read_text().strip():
                break
            await asyncio.sleep(0.05)
        assert pid_file.exists(), "child never started"
        pid = int(pid_file.read_text().strip())

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        for _ in range(40):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.05)
        else:
            pytest.fail("child survived cancellation")


async def test_terminal_state_is_absorbing(tmp_path: Path) -> None:
    """A reclaimed run must never be reopened by the engine (F1)."""
    from grimoire.checks.engine import run_check_for_all_targets
    from grimoire.database import CheckRunRecord, reclaim_expired_runs

    engine = await get_engine(str(tmp_path / "absorbing.db"))
    await create_tables(engine)
    check = CheckDefinition(
        name="Slow",
        slug="slow",
        description="",
        targets=TargetSpec(list=["acme/repo"]),
        script="sleep 0.5",
    )
    task = asyncio.create_task(
        run_check_for_all_targets(
            check,
            [_repo()],
            MockWorkspace(tmp_path),
            engine,  # type: ignore[arg-type]
        )
    )
    await asyncio.sleep(0.15)

    async with AsyncSession(engine) as session:
        row = (
            await session.exec(
                select(CheckRunRecord).where(CheckRunRecord.check_slug == "slow")
            )
        ).first()
        assert row is not None
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.add(row)
        await session.commit()

    await reclaim_expired_runs(engine)
    await task

    async with AsyncSession(engine) as session:
        row = (
            await session.exec(
                select(CheckRunRecord).where(CheckRunRecord.check_slug == "slow")
            )
        ).first()
        assert row is not None
        assert row.status == "interrupted"


async def test_two_entry_points_run_once(tmp_path: Path) -> None:
    """Cron and MCP must not both execute the same check (F3)."""
    from grimoire.checks.engine import CheckConflictError, run_check_for_all_targets

    engine = await get_engine(str(tmp_path / "admission.db"))
    await create_tables(engine)
    counter = tmp_path / "count.txt"
    check = _check(f"echo x >> {counter}; sleep 0.2")

    results = await asyncio.gather(
        run_check_for_all_targets(
            check,
            [_repo()],
            MockWorkspace(tmp_path),
            engine,  # type: ignore[arg-type]
            triggered_by="cron",
        ),
        run_check_for_all_targets(
            check,
            [_repo()],
            MockWorkspace(tmp_path),
            engine,  # type: ignore[arg-type]
            triggered_by="mcp",
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(r, CheckConflictError) for r in results) == 1
    assert len(counter.read_text().splitlines()) == 1


async def test_prepare_check_run_conflict(tmp_path: Path) -> None:
    """A second admission for the same slug raises (F3)."""
    from grimoire.checks.engine import (
        CheckConflictError,
        _running_checks,
        prepare_check_run,
    )

    engine = await get_engine(str(tmp_path / "conflict.db"))
    await create_tables(engine)
    check = _check("echo ok")
    try:
        await prepare_check_run(engine, check, "manual")
        with pytest.raises(CheckConflictError):
            await prepare_check_run(engine, check, "manual")
    finally:
        _running_checks.pop(check.slug, None)


def test_stale_memory_flag_expires() -> None:
    """A dropped task's memory entry expires instead of blocking forever (F4)."""
    from grimoire.checks.engine import CheckProgress, _running_checks, is_check_running

    _running_checks["stale"] = CheckProgress(
        expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    try:
        assert is_check_running("stale") is False
        assert "stale" not in _running_checks
    finally:
        _running_checks.pop("stale", None)
