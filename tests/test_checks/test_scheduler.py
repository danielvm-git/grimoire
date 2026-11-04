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
