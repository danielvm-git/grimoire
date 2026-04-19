"""Tests for the web page routes and HTMX partials."""

from __future__ import annotations

from httpx import AsyncClient


class TestDashboard:
    """Tests for GET / dashboard route."""

    async def test_dashboard_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_dashboard_contains_repo_names(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/")
        assert resp.status_code == 200
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_dashboard_contains_grimoire_title(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/")
        assert "Grimoire" in resp.text

    async def test_dashboard_shows_warning(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/")
        assert "Rate limit approaching" in resp.text


class TestRepositoryDetail:
    """Tests for GET /repo/{owner}/{name} route."""

    async def test_known_repo_returns_200(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "acme/api" in resp.text

    async def test_unknown_repo_returns_404(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/unknown/nope")
        assert resp.status_code == 404

    async def test_repo_detail_shows_workflows(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "CI" in resp.text
        assert "success" in resp.text

    async def test_repo_detail_shows_stale_issues(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Stale Issues" in resp.text
        assert "Fix legacy endpoint" in resp.text
        assert "Docs out of date" in resp.text
        assert "#42" in resp.text or "42" in resp.text

    async def test_repo_detail_shows_stale_prs(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Stale Pull Requests" in resp.text
        assert "Refactor auth module" in resp.text
        assert "charlie" in resp.text

    async def test_repo_detail_shows_last_activity(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Last Activity" in resp.text
        assert "2026-04-10" in resp.text

    async def test_repo_detail_shows_branches(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Branches" in resp.text
        # 8 total branches, 3 stale
        assert ">8<" in resp.text or ">8</div>" in resp.text

    async def test_repo_detail_stale_threshold_highlighting(self, web_client: AsyncClient) -> None:
        """acme/api has 2 stale out of 5 issues (40%) which exceeds 20% threshold → warning."""
        resp = await web_client.get("/repo/acme/api")
        assert "text-warning" in resp.text
        assert "40% of open" in resp.text

    async def test_repo_detail_no_warning_when_below_threshold(
        self, web_client: AsyncClient
    ) -> None:
        """acme/frontend has 0 stale issues → should show text-success."""
        resp = await web_client.get("/repo/acme/frontend")
        # Stale Issues box should show text-success (0 stale)
        assert "Stale Issues" not in resp.text or "text-success" in resp.text

    async def test_repo_without_stale_items_hides_sections(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/frontend")
        assert resp.status_code == 200
        # The card-level sections should not appear (stat boxes use different text)
        assert "Stale Issues</h2>" not in resp.text
        assert "Stale Pull Requests</h2>" not in resp.text


class TestActionsPage:
    """Tests for GET /actions route."""

    async def test_actions_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/actions")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_actions_shows_empty_state(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/actions")
        assert "No actions configured" in resp.text


class TestDashboardPartial:
    """Tests for GET /partials/dashboard-cards route."""

    async def test_partial_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=name&dir=asc")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_partial_contains_repos(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=name&dir=asc")
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_sort_name_asc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=name&dir=asc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert api_pos < frontend_pos

    async def test_sort_name_desc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=name&dir=desc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_sort_issues(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=issues&dir=desc")
        text = resp.text
        # acme/frontend has 10 issues, acme/api has 5 — frontend should come first
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_sort_last_activity(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=last_activity&dir=desc")
        text = resp.text
        # acme/frontend has 2026-04-12, acme/api has 2026-04-10 — frontend should come first
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_dashboard_shows_last_activity(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=name&dir=asc")
        assert "Last activity:" in resp.text

    async def test_dashboard_shows_branches(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-cards?sort=name&dir=asc")
        assert "8 branches" in resp.text
        assert "3 stale" in resp.text
        assert "4 branches" in resp.text


class TestDashboardListPartial:
    """Tests for GET /partials/dashboard-list route."""

    async def test_list_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-list?sort=name&dir=asc")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_list_contains_repos(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-list?sort=name&dir=asc")
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_list_sort_name_asc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-list?sort=name&dir=asc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert api_pos < frontend_pos

    async def test_list_sort_issues_desc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-list?sort=issues&dir=desc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_list_shows_warnings(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-list?sort=name&dir=asc")
        assert "⚠" in resp.text


class TestDashboardTablePartial:
    """Tests for GET /partials/dashboard-table route."""

    async def test_table_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-table?sort=name&dir=asc")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_table_contains_repos(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-table?sort=name&dir=asc")
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_table_has_table_structure(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-table?sort=name&dir=asc")
        assert "<table" in resp.text
        assert "<thead>" in resp.text
        assert "<tbody>" in resp.text

    async def test_table_sort_name_asc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-table?sort=name&dir=asc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert api_pos < frontend_pos

    async def test_table_sort_issues_desc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-table?sort=issues&dir=desc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_table_shows_sortable_headers(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-table?sort=name&dir=asc")
        assert "hx-get" in resp.text
        assert "/partials/dashboard-table" in resp.text

    async def test_table_shows_workflow_dots(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-table?sort=name&dir=asc")
        assert "dot-success" in resp.text
        assert "dot-failure" in resp.text


class TestActionRunPartial:
    """Tests for GET /partials/action-run/{run_id} route."""

    async def test_action_run_partial_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/action-run/1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


class TestCheckOutputPartial:
    """Tests for GET /partials/check-output/{result_id} route."""

    async def test_check_output_partial_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/check-output/1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


class TestCheckDisplay:
    """Tests for check display across dashboard views."""

    async def test_cards_show_check_dots(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/partials/dashboard-cards?sort=name&dir=asc")
        assert resp.status_code == 200
        assert "Checks" in resp.text
        assert "dot-pass" in resp.text
        assert "dot-fail" in resp.text

    async def test_cards_show_not_run_checks(self, web_client_with_checks: AsyncClient) -> None:
        """Watchdog targets both repos but only has results for some branches."""
        resp = await web_client_with_checks.get("/partials/dashboard-cards?sort=name&dir=asc")
        assert "dot-not-run" in resp.text

    async def test_list_show_check_dots(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/partials/dashboard-list?sort=name&dir=asc")
        assert resp.status_code == 200
        assert "dot-pass" in resp.text
        assert "dot-fail" in resp.text

    async def test_table_show_check_dots(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/partials/dashboard-table?sort=name&dir=asc")
        assert resp.status_code == 200
        assert ">Checks<" in resp.text
        assert "dot-pass" in resp.text
        assert "dot-fail" in resp.text

    async def test_repo_detail_shows_checks(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/repo/acme/api")
        assert resp.status_code == 200
        assert "Checks" in resp.text
        assert "Watchdog" in resp.text
        assert "dot-pass" in resp.text

    async def test_repo_detail_shows_not_run_for_untargeted(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        """acme/api doesn't match '-operator$' so charm-libs should not appear."""
        resp = await web_client_with_checks.get("/repo/acme/api")
        assert "Charm Libraries" not in resp.text

    async def test_repo_detail_shows_check_failure_badge(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/repo/acme/frontend")
        assert "1 failing" in resp.text

    async def test_check_output_loads_from_db(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/partials/check-output/1")
        assert resp.status_code == 200
        assert "OK" in resp.text

    async def test_dashboard_stats_bar_shows_checks(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/")
        assert resp.status_code == 200
        assert "Checks" in resp.text
        assert "1 failing" in resp.text


class TestChecksPage:
    """Tests for GET /checks route."""

    async def test_checks_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/checks")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_checks_shows_empty_state(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/checks")
        assert "No checks configured" in resp.text
        assert "data/checks/" in resp.text

    async def test_checks_shows_check_definitions(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert resp.status_code == 200
        assert "Watchdog" in resp.text
        assert "Charm Libraries" in resp.text

    async def test_checks_shows_descriptions(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "Always green sentinel" in resp.text
        assert "Check charm libs" in resp.text

    async def test_checks_shows_target_summaries(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "regex: .*" in resp.text
        assert "regex: -operator$" in resp.text

    async def test_checks_shows_toggle_buttons(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "/api/checks/watchdog/toggle" in resp.text
        assert "/api/checks/charm-libs/toggle" in resp.text

    async def test_checks_shows_run_buttons(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "/api/checks/watchdog/run" in resp.text
        assert "/api/checks/charm-libs/run" in resp.text

    async def test_checks_shows_result_counts(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/checks")
        # Watchdog has 1 pass + 1 fail from fixture data
        assert "1 passed" in resp.text
        assert "1 failed" in resp.text

    async def test_checks_shows_result_history(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "Latest Results" in resp.text
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_checks_empty_results_message(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/checks")
        assert "No check results yet" in resp.text

    async def test_checks_shows_script_preview(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "exit 0" in resp.text

    async def test_checks_navbar_active(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "Checks" in resp.text


class TestCheckResultsPartial:
    """Tests for GET /partials/check-results/{slug} route."""

    async def test_returns_results_for_slug(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/partials/check-results/watchdog")
        assert resp.status_code == 200
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_empty_when_no_results(self, web_client_with_checks: AsyncClient) -> None:
        resp = await web_client_with_checks.get("/partials/check-results/charm-libs")
        assert resp.status_code == 200
        assert "No results for this check" in resp.text
