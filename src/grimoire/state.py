"""Explicit run-state model shared by checks and actions.

Historically ``status`` was a bare string with transitions scattered across the
engines, routers, and startup cleanup. This module is the single vocabulary:

    queued ──▶ running ──▶ completed | failed | interrupted

``queued`` is a run that has been accepted (and persisted) but has not started
executing yet. ``running`` is non-terminal. The remaining states are terminal.
"""

from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    """Lifecycle states for a check or action run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


TERMINAL_RUN_STATES: frozenset[str] = frozenset(
    {
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.INTERRUPTED,
        RunState.CANCELLED,
    }
)

# Every status the application may persist. Anything else is a corrupt row and
# is reclaimed to ``interrupted`` rather than stranded forever.
ALL_RUN_STATES: frozenset[str] = frozenset(state.value for state in RunState)

# States in which a run has not reached a final outcome yet.
NON_TERMINAL_RUN_STATES: frozenset[str] = frozenset({RunState.QUEUED, RunState.RUNNING})

# States a run may be in when the process starts reclaiming leftovers.
RECLAIMABLE_RUN_STATES: tuple[str, ...] = (
    RunState.QUEUED.value,
    RunState.RUNNING.value,
)


def is_terminal(status: str) -> bool:
    """Return True when *status* is a final run outcome."""
    return status in TERMINAL_RUN_STATES
