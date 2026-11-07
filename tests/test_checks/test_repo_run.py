# story: e13s05
"""Tests for running all checks against a single repository."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.checks import engine as checks_engine
from grimoire.checks.engine import (
    CheckConflictError,
    clear_check_running,
    get_repo_run_progress,
    is_repo_run_active,
    reserve_checks_for_repo,
    run_reserved_checks_for_repo,
)
from grimoire.checks.loader import CheckDefinition
from grimoire.database import CheckResultRecord, create_tables, get_engine
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec


class MockWorkspace:
    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir

    async def reset_workdir(self, full_name: str, branch: str) -> Path:
        return self._workdir

    def get_workdir(self, full_name: str, branch: str) -> Path:
        return self._workdir

    def get_env(self) -> dict[str, str]:
        return {}


def _check(slug: str, script: str = "echo ok", enabled: bool = True) -> CheckDefinition:
    return CheckDefinition(
        name=slug.title(),
        slug=slug,
        description="d",
        targets=TargetSpec(list=["acme/a", "acme/b"]),
        script=script,
        enabled=enabled,
    )


REPOS = [
    TrackedRepository(full_name="acme/a", default_branch="main"),
    TrackedRepository(full_name="acme/b", default_branch="main"),
]


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    checks_engine._running_checks.clear()
    checks_engine._running_repos.clear()


async def _engine(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = await get_engine(str(tmp_path / "t.db"))
    await create_tables(engine)
    return engine


async def test_runs_only_the_requested_repo(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    checks = [_check("one"), _check("two")]
    plan = await reserve_checks_for_repo(engine, checks, "acme/a")
    results = await run_reserved_checks_for_repo(
        plan,
        REPOS,
        MockWorkspace(tmp_path),
        engine,  # type: ignore[arg-type]
    )
    assert {r.repo_full_name for r in results} == {"acme/a"}
    assert {r.check_slug for r in results} == {"one", "two"}
    async with AsyncSession(engine) as session:
        rows = (await session.exec(select(CheckResultRecord))).all()
    assert {r.repo_full_name for r in rows} == {"acme/a"}
    assert not is_repo_run_active("acme/a")


async def test_disabled_checks_are_not_reserved(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    plan = await reserve_checks_for_repo(
        engine, [_check("on"), _check("off", enabled=False)], "acme/a"
    )
    assert [c.slug for c, _ in plan.reserved] == ["on"]
    for c, _ in plan.reserved:
        clear_check_running(c.slug)


async def test_running_check_is_skipped_not_failed(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    busy = _check("busy")
    await reserve_checks_for_repo(engine, [busy], "acme/b")  # holds the slot
    plan = await reserve_checks_for_repo(engine, [busy, _check("free")], "acme/a")
    assert plan.skipped == ["busy"]
    assert [c.slug for c, _ in plan.reserved] == ["free"]


async def test_second_run_for_same_repo_conflicts(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    await reserve_checks_for_repo(engine, [_check("one")], "acme/a")
    with pytest.raises(CheckConflictError):
        await reserve_checks_for_repo(engine, [_check("two")], "acme/a")


async def test_progress_counts_checks(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    plan = await reserve_checks_for_repo(engine, [_check("x"), _check("y")], "acme/a")
    progress = get_repo_run_progress("acme/a")
    assert progress is not None and progress.total == 2 and progress.completed == 0
    await run_reserved_checks_for_repo(
        plan,
        REPOS,
        MockWorkspace(tmp_path),
        engine,  # type: ignore[arg-type]
    )
    assert get_repo_run_progress("acme/a") is None
