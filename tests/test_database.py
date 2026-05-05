"""Tests for the database setup."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from grimoire.database import create_tables, get_engine, get_session


@pytest.fixture
async def engine(tmp_path) -> AsyncEngine:
    """Create a temporary in-memory database engine."""
    db_path = str(tmp_path / "test.db")
    eng = await get_engine(db_path)
    await create_tables(eng)
    return eng


async def test_engine_creation(engine: AsyncEngine) -> None:
    """Engine is created and usable."""
    assert engine is not None


async def test_tables_created(engine: AsyncEngine) -> None:
    """All expected tables exist after create_tables."""
    from sqlmodel import text

    session = await get_session(engine)
    async with session:
        result = await session.exec(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")  # type: ignore[arg-type]
        )
        tables = {row[0] for row in result.all()}

    expected = {
        "check_run",
        "check_result",
        "check_toggle",
        "action_run",
        "action_run_repo",
        "cached_repository",
        "cached_issue",
        "cached_pull_request",
        "cached_workflow_status",
        "cached_etag",
        "stats_snapshot",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


async def test_session_usable(engine: AsyncEngine) -> None:
    """Can create a session and execute a simple query."""
    from grimoire.database import CheckToggleRecord

    session = await get_session(engine)
    async with session:
        record = CheckToggleRecord(check_slug="test-check", enabled=True)
        session.add(record)
        await session.commit()

        from sqlmodel import select

        result = await session.exec(select(CheckToggleRecord))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].check_slug == "test-check"
        assert rows[0].enabled is True


async def test_cleanup_stale_runs(engine: AsyncEngine) -> None:
    """cleanup_stale_runs marks 'running' records as 'interrupted'."""
    from grimoire.database import (
        ActionRunRecord,
        CheckRunRecord,
        cleanup_stale_runs,
    )

    session = await get_session(engine)
    async with session:
        session.add(
            CheckRunRecord(
                check_slug="c1", check_name="C1", triggered_by="manual", status="running"
            )
        )
        session.add(
            CheckRunRecord(
                check_slug="c2", check_name="C2", triggered_by="cron", status="completed"
            )
        )
        session.add(
            ActionRunRecord(
                action_slug="a1", action_name="A1", triggered_by="manual", status="running"
            )
        )
        await session.commit()

    await cleanup_stale_runs(engine)

    from sqlmodel import select

    session = await get_session(engine)
    async with session:
        c1 = (
            await session.exec(select(CheckRunRecord).where(CheckRunRecord.check_slug == "c1"))
        ).first()
        assert c1 is not None
        assert c1.status == "interrupted"
        assert c1.finished_at is not None

        c2 = (
            await session.exec(select(CheckRunRecord).where(CheckRunRecord.check_slug == "c2"))
        ).first()
        assert c2 is not None
        assert c2.status == "completed"

        a1 = (
            await session.exec(select(ActionRunRecord).where(ActionRunRecord.action_slug == "a1"))
        ).first()
        assert a1 is not None
        assert a1.status == "interrupted"
        assert a1.finished_at is not None


async def test_restore_check_toggles(engine: AsyncEngine) -> None:
    """restore_check_toggles applies persisted enabled state to check definitions."""
    from grimoire.database import CheckToggleRecord, restore_check_toggles

    session = await get_session(engine)
    async with session:
        session.add(CheckToggleRecord(check_slug="check-a", enabled=False))
        session.add(CheckToggleRecord(check_slug="check-b", enabled=True))
        await session.commit()

    # Simulate in-memory check definitions (duck-typed)
    class FakeCheck:
        def __init__(self, slug: str, enabled: bool = True) -> None:
            self.slug = slug
            self.enabled = enabled

    checks = [FakeCheck("check-a"), FakeCheck("check-b"), FakeCheck("check-c")]
    await restore_check_toggles(engine, checks)

    assert checks[0].enabled is False  # restored from DB
    assert checks[1].enabled is True  # restored (already True)
    assert checks[2].enabled is True  # no DB record, stays default


async def test_restore_action_toggles(engine: AsyncEngine) -> None:
    """restore_action_toggles applies persisted enabled state to action definitions."""
    from grimoire.database import ActionToggleRecord, restore_action_toggles

    session = await get_session(engine)
    async with session:
        session.add(ActionToggleRecord(action_slug="act-x", enabled=False))
        await session.commit()

    class FakeAction:
        def __init__(self, slug: str, enabled: bool = True) -> None:
            self.slug = slug
            self.enabled = enabled

    actions = [FakeAction("act-x"), FakeAction("act-y")]
    await restore_action_toggles(engine, actions)

    assert actions[0].enabled is False  # restored from DB
    assert actions[1].enabled is True  # no DB record, stays default
