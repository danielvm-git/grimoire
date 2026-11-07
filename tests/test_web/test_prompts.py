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


def test_workflow_prompt_includes_run_url() -> None:
    prompt = build_workflow_prompt("a/b", "main", "CI", "https://x/runs/1")
    assert "https://x/runs/1" in prompt
    assert "gh run view" in prompt


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
