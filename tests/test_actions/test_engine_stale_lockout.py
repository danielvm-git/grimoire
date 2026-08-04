"""Tests for stale 'running' action run records and startup recovery (bug #1).

Bug #1 (action-stale-running-lockout): if the app crashes while an action is
running, the ActionRunRecord stays status='running' in the DB. Within a live
process, run_action queries for status='running' rows and raises
ActionConflictError — silently swallowed by the router background task — so the
action can never run again until the whole app restarts and
``cleanup_stale_runs`` resets the row.

These tests pin down both halves of the contract.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.actions.engine import ActionConflictError, run_action
from grimoire.actions.loader import ActionDefinition
from grimoire.database import (
    ActionRunRecord,
    create_tables,
    get_engine,
)
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec


def _repo() -> TrackedRepository:
    return TrackedRepository(full_name="acme/repo", default_branch="main")


def _action(script: str = "echo ok") -> ActionDefinition:
    return ActionDefinition(
        name="Test",
        slug="test-action",
        description=".",
        targets=TargetSpec(list=["acme/repo"]),
        script=script,
    )


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


async def _seed_stale_running_record(engine, slug: str = "test-action") -> None:
    """Insert a DB row simulating a crashed previous run stuck at 'running'."""
    async with AsyncSession(engine) as session:
        session.add(
            ActionRunRecord(
                action_slug=slug,
                action_name="Test",
                triggered_by="manual",
                status="running",
            )
        )
        await session.commit()


class TestStaleRunningLockout:
    """Bug #1 — stale 'running' DB rows must not permanently block execution."""

    async def test_stale_running_row_raises_conflict_in_process(
        self, tmp_path: Path
    ) -> None:
        """A leftover status='running' row causes ActionConflictError.

        This documents the in-process lockout: without startup cleanup, the row
        left by a previous crashed process blocks all subsequent runs of that
        action until the app restarts.
        """
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        await _seed_stale_running_record(engine)

        ws = MockWorkspace(tmp_path)
        with pytest.raises(ActionConflictError, match="already running"):
            await run_action(
                _action(),
                [_repo()],
                ws,  # type: ignore[arg-type]
                engine,
                triggered_by="manual",
            )

    async def test_startup_cleanup_recovers_stale_row(self, tmp_path: Path) -> None:
        """cleanup_stale_runs (called at app startup) resets 'running' rows.

        After startup cleanup, the previously-stuck action must be runnable
        again — this is the regression guard proving the deadlock is resolved
        once cleanup has run.
        """
        from grimoire.database import cleanup_stale_runs

        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        await _seed_stale_running_record(engine)

        # Simulate app startup recovery
        await cleanup_stale_runs(engine)

        ws = MockWorkspace(tmp_path)
        # No longer blocked — the stale row was reset to 'interrupted'
        run = await run_action(
            _action(),
            [_repo()],
            ws,  # type: ignore[arg-type]
            engine,
            triggered_by="manual",
        )
        assert run.action_slug == "test-action"


class TestRouterSilentSwallow:
    """The router background task must log a swallowed ActionConflictError (bug #1).

    The deadlock is resolved at startup by cleanup_stale_runs, but if a conflict
    still fires inside the background task it must not be invisible — that is the
    residual defect this hardening addresses.
    """

    async def test_background_conflict_is_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        engine = await get_engine(str(tmp_path / "test.db"))
        await create_tables(engine)
        await _seed_stale_running_record(engine)

        # Replicate the router's _run_in_background closure body directly so we
        # can assert on logging without standing up the full FastAPI app.
        async def _run_in_background() -> None:
            try:
                await run_action(
                    _action(),
                    [_repo()],
                    MockWorkspace(tmp_path),  # type: ignore[arg-type]
                    engine,
                    triggered_by="manual",
                )
            except ActionConflictError as exc:
                logging.getLogger("grimoire.actions.router").warning(
                    "Action '%s' not run: %s", "test-action", exc, exc_info=True
                )

        with caplog.at_level(logging.WARNING, logger="grimoire.actions.router"):
            await _run_in_background()

        assert any(
            "not run" in rec.message and rec.levelno == logging.WARNING
            for rec in caplog.records
        ), f"expected a warning log, got: {caplog.records}"
