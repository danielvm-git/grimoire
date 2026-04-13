"""APScheduler v3 integration for periodic action execution."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from grimoire.actions.engine import run_action

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.actions.loader import ActionDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager


def register_actions(
    scheduler: AsyncIOScheduler | BackgroundScheduler,
    actions: list[ActionDefinition],
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
) -> None:
    """Register actions that have a ``schedule`` with the scheduler.

    Actions without a schedule are manual-only and are not registered.
    """
    for action in actions:
        if not action.schedule:
            continue

        trigger = CronTrigger.from_crontab(action.schedule)

        def _make_job(a: ActionDefinition) -> object:
            """Return an async wrapper that ``AsyncIOScheduler`` can invoke."""

            async def _job() -> None:
                await run_action(a, repos, workspace, engine, triggered_by="cron")

            if hasattr(scheduler, "_eventloop"):
                return _job  # AsyncIOScheduler

            def _sync_job() -> None:
                asyncio.get_event_loop().run_until_complete(
                    run_action(a, repos, workspace, engine, triggered_by="cron")
                )

            return _sync_job

        scheduler.add_job(
            _make_job(action),
            trigger=trigger,
            id=f"action:{action.slug}",
            replace_existing=True,
        )
