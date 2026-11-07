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


# ---------------------------------------------------------------------------
# SQLITE_BUSY handling
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from grimoire.db_exec import is_lock_error, retry_on_lock  # noqa: E402


def _locked_error() -> OperationalError:
    return OperationalError(
        "INSERT INTO cached_etag", {}, Exception("database is locked")
    )


def test_is_lock_error_detects_sqlite_busy() -> None:
    """A SQLITE_BUSY OperationalError is recognized as a lock error."""
    assert is_lock_error(_locked_error()) is True


def test_is_lock_error_ignores_other_errors() -> None:
    """Non-lock errors (and non-OperationalError exceptions) are not lock errors."""
    assert is_lock_error(ValueError("database is locked")) is False
    assert (
        is_lock_error(OperationalError("INSERT", {}, Exception("no such table")))
        is False
    )


async def test_retry_on_lock_succeeds_after_release() -> None:
    """retry_on_lock waits out a transient SQLITE_BUSY and returns the result."""
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _locked_error()
        return "ok"

    result = await retry_on_lock(operation, delays=(0.0, 0.0, 0.0))
    assert result == "ok"
    assert attempts == 3


async def test_retry_on_lock_reraises_other_errors() -> None:
    """Non-lock errors are never retried."""
    attempts = 0

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await retry_on_lock(operation, delays=(0.0, 0.0, 0.0))
    assert attempts == 1


async def test_retry_on_lock_gives_up_after_attempts() -> None:
    """A persistent lock still surfaces after the retry budget is spent."""
    attempts = 0

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise _locked_error()

    with pytest.raises(OperationalError):
        await retry_on_lock(operation, attempts=3, delays=(0.0, 0.0, 0.0))
    assert attempts == 3


async def test_retry_on_lock_does_not_block_event_loop() -> None:
    """Backoff sleeps yield control so other tasks keep running."""
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        for _ in range(5):
            ticks += 1
            await asyncio.sleep(0.01)

    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise _locked_error()
        return "ok"

    result, _ = await asyncio.gather(retry_on_lock(operation, delays=(0.02,)), ticker())
    assert result == "ok"
    assert ticks == 5, "event loop was blocked by the retry backoff"
