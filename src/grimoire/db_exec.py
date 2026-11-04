"""Helpers for running non-ORM statements on SQLModel's AsyncSession.

SQLModel's ``AsyncSession.execute()`` emits a DeprecationWarning urging
``session.exec()``. That advice applies only to ORM ``select()`` queries; for raw
``text()`` SQL and Core DML (``delete()``, ``insert()``) ``session.execute()`` is
the correct API. :func:`exec_raw` wraps it and silences the misleading nag so logs
and test output stay clean.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

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
