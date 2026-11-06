# story: e01s03
"""Tests for the raw-statement execution helper."""

from __future__ import annotations

import warnings

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.db_exec import exec_raw


async def test_exec_raw_suppresses_session_execute_nag() -> None:
    """exec_raw() silences SQLModel's misleading session.execute() nag.

    Uses a real AsyncSession so the SQLModel wrapper actually emits its warning.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with AsyncSession(engine) as session:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = await exec_raw(session, text("SELECT 1"))
                assert result is not None
    finally:
        await engine.dispose()

    nags = [w for w in caught if "session.exec" in str(w.message)]
    assert nags == [], f"SQLModel session.execute() nag leaked: {len(nags)} nags"


async def test_exec_raw_passes_params() -> None:
    """exec_raw() forwards bound parameters to session.execute()."""
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with AsyncSession(engine) as session:
            result = await exec_raw(session, text("SELECT :value"), params={"value": 7})
            assert result.scalar_one() == 7
    finally:
        await engine.dispose()
