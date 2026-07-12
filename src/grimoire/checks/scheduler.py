"""APScheduler v3 integration for periodic check execution."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from grimoire.checks.engine import run_check_for_all_targets

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from sqlalchemy.ext.asyncio import AsyncEngine

    from grimoire.checks.loader import CheckDefinition
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager


def register_checks(
    scheduler: AsyncIOScheduler | BackgroundScheduler,
    checks: list[CheckDefinition],
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
) -> None:
    """Register checks that have an explicit cron ``schedule`` with the scheduler.

    Checks *without* a schedule are driven by the data-refresh cycle instead
    (see ``_do_refresh`` in ``app.py``).
    """
    for check in checks:
        if not check.enabled:
            continue

        if not check.schedule:
            continue

        trigger = CronTrigger.from_crontab(check.schedule)

        def _make_job(c: CheckDefinition) -> object:
            """Return an async wrapper that ``AsyncIOScheduler`` can invoke."""

            async def _job() -> None:
                await run_check_for_all_targets(
                    c, repos, workspace, engine, triggered_by="cron"
                )

            # APScheduler 3 AsyncIOScheduler expects a callable; for sync
            # schedulers fall back to running the coroutine in the loop.
            if hasattr(scheduler, "_eventloop"):
                return _job  # AsyncIOScheduler

            # BackgroundScheduler — wrap in run-until-complete
            def _sync_job() -> None:
                asyncio.get_event_loop().run_until_complete(
                    run_check_for_all_targets(
                        c, repos, workspace, engine, triggered_by="cron"
                    )
                )

            return _sync_job

        scheduler.add_job(
            _make_job(check),
            trigger=trigger,
            id=f"check:{check.slug}",
            replace_existing=True,
        )
