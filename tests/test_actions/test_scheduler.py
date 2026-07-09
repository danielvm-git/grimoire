"""Tests for the actions scheduler."""

from __future__ import annotations

from unittest.mock import MagicMock

from grimoire.actions.loader import ActionDefinition
from grimoire.actions.scheduler import register_actions
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec


def _action(
    slug: str, schedule: str | None = None, enabled: bool = True
) -> ActionDefinition:
    return ActionDefinition(
        name=f"Action {slug}",
        slug=slug,
        description="test",
        targets=TargetSpec(list=["acme/repo"]),
        script="echo ok",
        schedule=schedule,
        enabled=enabled,
    )


class TestRegisterActions:
    def test_only_cron_actions_registered(self) -> None:
        """Actions without an explicit schedule should NOT be registered."""
        scheduler = MagicMock()
        scheduler._eventloop = True  # simulate AsyncIOScheduler

        actions = [
            _action("cron-action", schedule="0 */6 * * *"),
            _action("manual-action"),  # no schedule
        ]
        repos = [TrackedRepository(full_name="acme/repo", default_branch="main")]

        register_actions(scheduler, actions, repos, MagicMock(), MagicMock())

        assert scheduler.add_job.call_count == 1
        call_kwargs = scheduler.add_job.call_args
        assert call_kwargs[1]["id"] == "action:cron-action"

    def test_disabled_actions_not_registered(self) -> None:
        """Disabled actions should NOT be registered regardless of schedule."""
        scheduler = MagicMock()
        scheduler._eventloop = True

        actions = [
            _action("disabled-cron", schedule="0 0 * * *", enabled=False),
            _action("disabled-manual", enabled=False),
        ]
        repos = [TrackedRepository(full_name="acme/repo", default_branch="main")]

        register_actions(scheduler, actions, repos, MagicMock(), MagicMock())

        assert scheduler.add_job.call_count == 0
