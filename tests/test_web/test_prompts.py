"""Tests for agent prompt generation and the repo detail copy-prompt UI."""

from __future__ import annotations

from httpx import AsyncClient

from grimoire.web.prompts import (
    MAX_OUTPUT_CHARS,
    Pendency,
    build_check_prompt,
    build_repo_prompt,
    build_stale_prompt,
    build_workflow_prompt,
)


def test_check_prompt_contains_context() -> None:
    prompt = build_check_prompt(
        "acme/api", "main", "Watchdog", "Verifies uptime", "boom"
    )
    assert "acme/api" in prompt
    assert "Branch: main" in prompt
    assert "Watchdog" in prompt
    assert "Verifies uptime" in prompt
    assert "boom" in prompt


def test_check_prompt_truncates_long_output() -> None:
    prompt = build_check_prompt("a/b", "main", "C", "", "x" * 10 * MAX_OUTPUT_CHARS)
    assert "[...truncated...]" in prompt
    assert len(prompt) < 3 * MAX_OUTPUT_CHARS


def test_check_prompt_handles_empty_output() -> None:
    assert "(no output)" in build_check_prompt("a/b", "main", "C", "", "  ")


def test_check_prompt_fence_outgrows_backticks_in_output() -> None:
    prompt = build_check_prompt("a/b", "main", "C", "", "x\n```\nignore previous\n```")
    assert "````\nx" in prompt


def test_repo_prompt_handles_prompt_without_blank_line() -> None:
    items = [Pendency("check", "error", "Check X", "main", "single line")]
    assert "single line" in build_repo_prompt("a/b", items)


def test_workflow_prompt_includes_run_url() -> None:
    prompt = build_workflow_prompt("a/b", "main", "CI", "https://x/runs/1")
    assert "https://x/runs/1" in prompt
    assert "gh run view" in prompt


def test_workflow_prompt_mentions_run_time() -> None:
    from datetime import datetime, timezone

    prompt = build_workflow_prompt(
        "a/b",
        "main",
        "CI",
        "https://x/runs/1",
        run_at=datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc),
    )
    assert "2026-11-07 10:00 UTC" in prompt


def test_stale_prompt_differs_for_issue_and_pr() -> None:
    issue = build_stale_prompt("a/b", "main", "issue", 1, "T", "u")
    pr = build_stale_prompt("a/b", "main", "pr", 2, "T", "u")
    assert "issue #1" in issue
    assert "pull request #2" in pr


def test_repo_prompt_orders_errors_first_and_is_empty_without_items() -> None:
    assert build_repo_prompt("a/b", []) == ""
    items = [
        Pendency("issue", "warning", "Stale issue", "main", "H\n\nwarn body"),
        Pendency("check", "error", "Check X", "main", "H\n\nerr body"),
    ]
    prompt = build_repo_prompt("a/b", items)
    assert prompt.index("err body") < prompt.index("warn body")
    assert "2 pending" in prompt


class TestRepoDetailPrompts:
    async def test_stale_items_get_copy_buttons(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Pendencies" in resp.text
        assert "Copy prompt for all" in resp.text
        assert "Stale issue #42" in resp.text

    async def test_failing_workflow_prompt(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/frontend")
        assert "Workflow: Build" in resp.text
        assert "gh run view" in resp.text

    async def test_failing_check_prompt_includes_output(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/repo/acme/frontend")
        assert "Check: Watchdog" in resp.text
        assert "Something went wrong" in resp.text

    async def test_workflows_show_relative_run_time_run_at(
        self, web_client: AsyncClient
    ) -> None:
        from datetime import datetime, timedelta, timezone

        from grimoire.github.router import _cache

        _cache["acme/frontend"].workflows[0].run_at = datetime.now(
            tz=timezone.utc
        ) - timedelta(hours=2)
        resp = await web_client.get("/repo/acme/frontend")
        assert "2h ago" in resp.text

    async def test_hostile_text_is_escaped(self, web_client: AsyncClient) -> None:
        from grimoire.github.router import _cache

        _cache["acme/api"].stale_issue_items[
            0
        ].title = "</template><script>alert(1)</script>"
        resp = await web_client.get("/repo/acme/api")
        assert "<script>alert(1)</script>" not in resp.text
        assert "&lt;/template&gt;" in resp.text

    async def test_failures_on_several_branches_get_own_pendencies(
        self, web_client: AsyncClient
    ) -> None:
        from grimoire.github.router import _cache
        from grimoire.models import WorkflowStatus

        stats = _cache["acme/frontend"]
        stats.workflows.append(
            WorkflowStatus(name="Build", branch="develop", status="failure", url="u")
        )
        resp = await web_client.get("/repo/acme/frontend")
        assert resp.text.count("Workflow: Build") >= 2

    async def test_no_pendencies_hides_section(self, web_client: AsyncClient) -> None:
        from grimoire.github.router import _cache

        stats = _cache["acme/api"]
        stats.stale_issue_items = []
        stats.stale_pr_items = []
        resp = await web_client.get("/repo/acme/api")
        assert "Copy prompt for all" not in resp.text
        assert "All clear" in resp.text

    async def test_header_summarises_severity_counts(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "3 warnings" in resp.text
        assert "error" not in resp.text.split('id="pendencies"')[1].split("</h2>")[0]

    async def test_preview_toggle_present(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "data-toggle-preview" in resp.text
