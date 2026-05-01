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
