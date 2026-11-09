"""APScheduler v3 integration for periodic check execution."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.triggers.cron import CronTrigger

from grimoire.checks.engine import CheckConflictError, run_check_for_all_targets

logger = logging.getLogger(__name__)

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
                # Re-check at fire time: toggling enabled does not re-register
                # jobs, so this guard is what makes a disable take effect now.
                if not c.enabled:
                    return
                try:
                    await run_check_for_all_targets(
                        c, repos, workspace, engine, triggered_by="cron"
                    )
                except CheckConflictError:
                    logger.info("Check '%s' already running; cron skipped", c.slug)

            # APScheduler 3 AsyncIOScheduler expects a callable; for sync
            # schedulers fall back to running the coroutine in the loop.
            if hasattr(scheduler, "_eventloop"):
                return _job  # AsyncIOScheduler

            # BackgroundScheduler — wrap in run-until-complete
            def _sync_job() -> None:
                if not c.enabled:
                    return
                try:
                    asyncio.get_event_loop().run_until_complete(
                        run_check_for_all_targets(
                            c, repos, workspace, engine, triggered_by="cron"
                        )
                    )
                except CheckConflictError:
                    logger.info("Check '%s' already running; cron skipped", c.slug)

            return _sync_job

        scheduler.add_job(
            _make_job(check),
            trigger=trigger,
            id=f"check:{check.slug}",
            replace_existing=True,
        )


async def run_all_checks_once(
    checks: list[CheckDefinition],
    repos: list[TrackedRepository],
    workspace: WorkspaceManager,
    engine: AsyncEngine,
    *,
    triggered_by: str = "startup",
    concurrency: int = 5,
    enabled: bool = True,
) -> int:
    """Run every enabled check once, regardless of its schedule.

    A deploy used to start with nothing to show: cron checks waited for their
    next window and schedule-less checks only ran after a data refresh. Running
    them once at startup gives the dashboard real results immediately; the cron
    schedule then takes over as usual (BUG-2026-11-09T000002).

    Returns the number of checks that were started. A check that is already
    running (initial refresh, cron, manual run) or raises is skipped so one
    problem cannot stop the rest of the startup pass.
    """
    if not enabled:
        logger.info("Checks run-on-startup is disabled by config")
        return 0

    pending = [c for c in checks if c.enabled]
    if not pending:
        return 0

    sem = asyncio.Semaphore(concurrency)
    started = 0

    async def _run(check: CheckDefinition) -> None:
        nonlocal started
        async with sem:
            if not check.enabled:  # toggled off while the pass was running
                return
            try:
                await run_check_for_all_targets(
                    check, repos, workspace, engine, triggered_by=triggered_by
                )
                started += 1
            except CheckConflictError:
                logger.info(
                    "Check '%s' already running; startup pass skipped it", check.slug
                )
            except Exception:
                logger.exception("Startup check '%s' failed", check.slug)

    logger.info("Running %d check(s) at startup before scheduling", len(pending))
    await asyncio.gather(*(_run(c) for c in pending))
    logger.info("Startup check pass started %d check(s)", started)
    return started
