"""Tests for the check execution engine."""

from __future__ import annotations

from pathlib import Path

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

            stmt = select(CheckResultRecord).where(CheckResultRecord.check_slug == "test-check")
            rows = (await session.exec(stmt)).all()

        assert len(rows) == 1
        assert rows[0].passed is True
        assert "persisted" in rows[0].output
