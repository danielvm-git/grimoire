"""FastAPI application factory for Grimoire."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from grimoire.actions.loader import load_actions
from grimoire.actions.router import router as actions_router
from grimoire.actions.router import set_actions_state
from grimoire.actions.scheduler import register_actions
from grimoire.checks.loader import load_checks
from grimoire.checks.router import router as checks_router
from grimoire.checks.router import set_checks_state
from grimoire.checks.scheduler import register_checks
from grimoire.config import load_config
from grimoire.database import create_tables, get_engine
from grimoire.github.client import GitHubClient
from grimoire.github.router import (
    _cache,
    _last_refresh,
    refresh_router,
    set_refresh_callback,
    update_cache,
)
from grimoire.github.router import (
    router as repos_router,
)
from grimoire.github.service import refresh_all_stats
from grimoire.observability.logging import setup_logging
from grimoire.observability.metrics import router as metrics_router
from grimoire.web.router import router as web_router
from grimoire.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    setup_logging()
    logger.info("Grimoire starting up")

    scheduler: AsyncIOScheduler | None = None
    client: GitHubClient | None = None

    try:
        config = load_config()
    except FileNotFoundError as exc:
        logger.warning("Config not loaded — running in empty mode: %s", exc)
        yield
        return

    # Database
    engine = await get_engine(str(config.database_path))
    await create_tables(engine)

    # GitHub client
    client = GitHubClient(config.github.token, engine)

    # Initial data refresh
    try:
        repos, stats = await refresh_all_stats(config, client)
        update_cache(repos, stats)
        logger.info("Initial refresh complete — %d repositories loaded", len(repos))
    except Exception:
        logger.exception("Initial data refresh failed")
        repos, stats = [], []

    # Workspace manager
    workspace = WorkspaceManager(config)

    # Checks & actions
    checks = load_checks(config.data_dir)
    actions = load_actions(config.data_dir)

    set_checks_state(checks, repos, workspace, engine)
    set_actions_state(actions, repos, workspace, engine)

    # Refresh callback for POST /api/refresh
    async def _do_refresh() -> None:
        refreshed_repos, refreshed_stats = await refresh_all_stats(config, client)
        update_cache(refreshed_repos, refreshed_stats)
        set_checks_state(checks, refreshed_repos, workspace, engine)
        set_actions_state(actions, refreshed_repos, workspace, engine)

    set_refresh_callback(_do_refresh)

    # Scheduler
    scheduler = AsyncIOScheduler()

    # Periodic data refresh
    scheduler.add_job(
        _do_refresh,
        trigger="interval",
        minutes=config.refresh_interval_minutes,
        id="data-refresh",
        replace_existing=True,
    )

    register_checks(scheduler, checks, repos, workspace, engine, config.refresh_interval_minutes)
    register_actions(scheduler, actions, repos, workspace, engine)

    scheduler.start()
    logger.info("Scheduler started (refresh every %d min)", config.refresh_interval_minutes)

    yield

    # Shutdown
    if scheduler:
        scheduler.shutdown(wait=False)
    if client:
        await client.close()
    logger.info("Grimoire shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Grimoire",
        description="Self-hostable GitHub repository monitoring dashboard",
        version="0.1.0",
        lifespan=lifespan,
    )

    # API routers
    app.include_router(repos_router, prefix="/api")
    app.include_router(refresh_router, prefix="/api")
    app.include_router(checks_router, prefix="/api")
    app.include_router(actions_router, prefix="/api")

    # Observability
    app.include_router(metrics_router)

    # Web pages
    app.include_router(web_router)

    # Static files
    static_dir = Path(__file__).parent / "web" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health", tags=["health"])
    async def health() -> JSONResponse:
        """Health check endpoint."""
        status = "ok"
        details: dict[str, object] = {}

        if _last_refresh:
            age = (datetime.now(tz=timezone.utc) - _last_refresh).total_seconds()
            details["cache_age_seconds"] = int(age)

        if _cache:
            details["tracked_repos"] = len(_cache)

        return JSONResponse({"status": status, "version": "0.1.0", **details})

    return app
