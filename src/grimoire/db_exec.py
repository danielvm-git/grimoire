"""Helpers for running non-ORM statements on SQLModel's AsyncSession.

SQLModel's ``AsyncSession.execute()`` emits a DeprecationWarning urging
``session.exec()``. That advice applies only to ORM ``select()`` queries; for raw
``text()`` SQL and Core DML (``delete()``, ``insert()``) ``session.execute()`` is
the correct API. :func:`exec_raw` wraps it and silences the misleading nag so logs
and test output stay clean.
"""

from __future__ import annotations

import asyncio
import logging
import warnings
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from sqlalchemy.exc import OperationalError

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Markers SQLite uses when a write cannot obtain the database lock.
_LOCK_MARKERS = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
    "database is busy",
)

# Retrying SQLITE_BUSY is always safe: the failed statement never took effect.
DEFAULT_LOCK_RETRIES = 4
DEFAULT_LOCK_BACKOFF_SECONDS = (0.05, 0.15, 0.35, 0.75)

# Plain regex string (not re.compile) consumed by warnings.filterwarnings().
# The warning text starts with whitespace and an emoji, so the pattern must not
# be anchored at the start (filterwarnings matches from position 0).
_SESSION_EXEC_NAG = r"[\s\S]*You probably want to use `session\.exec\(\)` instead of `session\.execute\(\)`"


async def exec_raw(
    session: AsyncSession,
    statement: Any,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    """Execute a raw ``text()``/Core statement, suppressing SQLModel's nag."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=_SESSION_EXEC_NAG, category=DeprecationWarning
        )
        if params:
            return await session.execute(statement, params=params)
        return await session.execute(statement)


def is_lock_error(exc: BaseException) -> bool:
    """Return True when *exc* is SQLite reporting a locked/busy database."""
    if not isinstance(exc, OperationalError):
        return False
    detail = f"{exc} {getattr(exc, 'orig', '')}".lower()
    return any(marker in detail for marker in _LOCK_MARKERS)


async def retry_on_lock(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = DEFAULT_LOCK_RETRIES,
    delays: tuple[float, ...] = DEFAULT_LOCK_BACKOFF_SECONDS,
) -> T:
    """Run *operation*, retrying while SQLite reports the database is locked.

    SQLite allows a single writer, so concurrent coroutines can collide even
    after ``busy_timeout``. A retry is safe because a statement that failed to
    acquire the lock never took effect. Non-lock errors propagate immediately.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except OperationalError as exc:
            if not is_lock_error(exc) or attempt >= attempts:
                raise
            delay = delays[min(attempt - 1, len(delays) - 1)] if delays else 0.0
            logger.warning(
                "SQLite database locked (attempt %d/%d); retrying in %.2fs",
                attempt,
                attempts,
                delay,
            )
            await asyncio.sleep(delay)

    raise AssertionError("unreachable: retry loop exhausted")  # pragma: no cover
