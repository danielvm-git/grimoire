"""Tests for RepoViewModel health_status property."""

from __future__ import annotations

from grimoire.web.router import RepoViewModel


def _make_vm(**overrides: object) -> RepoViewModel:
    """Create a RepoViewModel with sensible defaults, overriding as needed."""
    defaults: dict[str, object] = {
        "full_name": "org/repo",
        "branches": ["main"],
        "source": "team:obs",
        "open_issues": 0,
        "stale_issues": 0,
        "open_prs": 0,
        "stale_prs": 0,
        "workflow_failures": 0,
        "check_failures": 0,
        "check_warnings": 0,
        "warnings": [],
        "workflows_by_branch": {},
        "checks_by_branch": {},
    }
    defaults.update(overrides)
    return RepoViewModel(**defaults)  # type: ignore[arg-type]


class TestHealthStatus:
    """RepoViewModel.health_status logic."""

    def test_ok_when_everything_clean(self) -> None:
        assert _make_vm().health_status == "ok"

    def test_error_on_workflow_failure(self) -> None:
        assert _make_vm(workflow_failures=1).health_status == "error"

    def test_error_on_check_failure(self) -> None:
        assert _make_vm(check_failures=1).health_status == "error"

    def test_warning_on_stale_issues(self) -> None:
        assert _make_vm(stale_issues=3).health_status == "warning"

    def test_warning_on_stale_prs(self) -> None:
        assert _make_vm(stale_prs=2).health_status == "warning"

    def test_check_warnings_do_not_affect_health(self) -> None:
        """Warning-severity check failures should NOT influence health."""
        vm = _make_vm(check_warnings=5)
        assert vm.health_status == "ok"

    def test_error_takes_priority_over_warning(self) -> None:
        vm = _make_vm(workflow_failures=1, stale_issues=3)
        assert vm.health_status == "error"
