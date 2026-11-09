# story: e04s04
"""Tests for the checks scheduler."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from grimoire.checks.loader import CheckDefinition
from grimoire.checks.scheduler import register_checks
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec


def _check(
    slug: str, schedule: str | None = None, enabled: bool = True
) -> CheckDefinition:
    return CheckDefinition(
        name=f"Check {slug}",
        slug=slug,
        description="test",
        targets=TargetSpec(list=["acme/repo"]),
        script="echo ok",
        schedule=schedule,
        enabled=enabled,
    )


class TestRegisterChecks:
    def test_only_cron_checks_registered(self) -> None:
        """Checks without an explicit schedule should NOT be registered."""
        scheduler = MagicMock()
        scheduler._eventloop = True  # simulate AsyncIOScheduler

        checks = [
            _check("cron-check", schedule="0 */6 * * *"),
            _check("default-check"),  # no schedule
        ]
        repos = [TrackedRepository(full_name="acme/repo", default_branch="main")]

        register_checks(scheduler, checks, repos, MagicMock(), MagicMock())

        # Only the cron check should be registered
        assert scheduler.add_job.call_count == 1
        call_kwargs = scheduler.add_job.call_args
        assert call_kwargs[1]["id"] == "check:cron-check"

    def test_disabled_checks_not_registered(self) -> None:
        """Disabled checks should NOT be registered regardless of schedule."""
        scheduler = MagicMock()
        scheduler._eventloop = True

        checks = [
            _check("disabled-cron", schedule="0 0 * * *", enabled=False),
            _check("disabled-default", enabled=False),
        ]
        repos = [TrackedRepository(full_name="acme/repo", default_branch="main")]

        register_checks(scheduler, checks, repos, MagicMock(), MagicMock())

        assert scheduler.add_job.call_count == 0

    def test_empty_checks_list(self) -> None:
        """No jobs should be registered when there are no checks."""
        scheduler = MagicMock()

        register_checks(scheduler, [], [], MagicMock(), MagicMock())

        assert scheduler.add_job.call_count == 0


async def test_scheduled_check_skips_when_disabled_at_fire_time(
    monkeypatch: Any,
) -> None:
    """Toggling a check off must stop cron execution without a restart."""
    calls: list[object] = []

    async def fake_run(*args: object, **kwargs: object) -> None:
        calls.append(args)

    monkeypatch.setattr("grimoire.checks.scheduler.run_check_for_all_targets", fake_run)

    check = _check("live", schedule="* * * * *")
    scheduler = MagicMock()
    scheduler._eventloop = True
    register_checks(scheduler, [check], [], MagicMock(), MagicMock())
    job = scheduler.add_job.call_args[0][0]

    check.enabled = False
    await job()
    assert calls == []

    check.enabled = True
    await job()
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Startup run (BUG-2026-11-09T000002 — checks waited for their cron after deploy)
# ---------------------------------------------------------------------------

import grimoire.checks.scheduler as sched_mod  # noqa: E402


def _startup_check(
    slug: str, *, enabled: bool = True, schedule: str | None = "0 3 * * *"
):
    from grimoire.checks.loader import CheckDefinition
    from grimoire.targeting import TargetSpec

    return CheckDefinition(
        name=slug.title(),
        slug=slug,
        description="",
        targets=TargetSpec(regex=".*"),
        script="exit 0",
        schedule=schedule,
        enabled=enabled,
    )


async def test_run_all_checks_once_runs_every_enabled_check(monkeypatch) -> None:
    """Every enabled check runs at startup — not just the cron-less ones."""
    from grimoire.models import TrackedRepository

    checks = [
        _startup_check("scheduled"),  # has a cron schedule
        _startup_check("unscheduled", schedule=None),
        _startup_check("disabled", enabled=False),
    ]
    ran: list[str] = []

    async def fake_run(check, repos, workspace, engine, triggered_by="manual", **kw):
        ran.append(f"{check.slug}:{triggered_by}")
        return []

    monkeypatch.setattr(sched_mod, "run_check_for_all_targets", fake_run)
    started = await sched_mod.run_all_checks_once(
        checks,
        [TrackedRepository(full_name="acme/one", default_branch="main")],
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        triggered_by="startup",
    )

    assert started == 2
    assert sorted(ran) == ["scheduled:startup", "unscheduled:startup"]


async def test_run_all_checks_once_skips_conflicts(monkeypatch) -> None:
    """A check already running (initial refresh, cron) is skipped, not fatal."""
    from grimoire.checks.engine import CheckConflictError
    from grimoire.models import TrackedRepository

    calls: list[str] = []

    async def fake_run(check, repos, workspace, engine, triggered_by="manual", **kw):
        calls.append(check.slug)
        if check.slug == "busy":
            raise CheckConflictError("already running")
        return []

    monkeypatch.setattr(sched_mod, "run_check_for_all_targets", fake_run)
    started = await sched_mod.run_all_checks_once(
        [_startup_check("busy"), _startup_check("free")],
        [TrackedRepository(full_name="acme/one", default_branch="main")],
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )

    assert started == 1
    assert sorted(calls) == ["busy", "free"]


async def test_run_all_checks_once_survives_a_failing_check(monkeypatch) -> None:
    """One broken check must not stop the rest of the startup run."""
    from grimoire.models import TrackedRepository

    async def fake_run(check, repos, workspace, engine, triggered_by="manual", **kw):
        if check.slug == "boom":
            raise RuntimeError("kaboom")
        return []

    monkeypatch.setattr(sched_mod, "run_check_for_all_targets", fake_run)
    started = await sched_mod.run_all_checks_once(
        [_startup_check("boom"), _startup_check("fine")],
        [TrackedRepository(full_name="acme/one", default_branch="main")],
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )

    assert started == 1


async def test_run_all_checks_once_respects_the_switch(monkeypatch) -> None:
    """`checks.run_on_startup: false` leaves the deploy quiet."""
    from grimoire.models import TrackedRepository

    calls: list[str] = []

    async def fake_run(check, repos, workspace, engine, triggered_by="manual", **kw):
        calls.append(check.slug)
        return []

    monkeypatch.setattr(sched_mod, "run_check_for_all_targets", fake_run)
    started = await sched_mod.run_all_checks_once(
        [_startup_check("a"), _startup_check("b")],
        [TrackedRepository(full_name="acme/one", default_branch="main")],
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        enabled=False,
    )

    assert started == 0
    assert calls == []
