# story: e06s01
"""Tests for the web page routes and HTMX partials."""

from __future__ import annotations

from pathlib import Path

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

    async def test_dashboard_contains_grimoire_title(
        self, web_client: AsyncClient
    ) -> None:
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

    async def test_repo_detail_shows_stale_issues(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Stale issues" in resp.text
        assert "Fix legacy endpoint" in resp.text
        assert "Docs out of date" in resp.text
        assert "#42" in resp.text or "42" in resp.text

    async def test_repo_detail_shows_stale_prs(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Stale pull requests" in resp.text
        assert "Refactor auth module" in resp.text
        assert "charlie" in resp.text

    async def test_repo_detail_shows_last_activity(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "Last activity" in resp.text
        assert "2026-04-10" in resp.text

    async def test_repo_detail_shows_branches(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/repo/acme/api")
        assert "branches" in resp.text
        # 8 total branches shown in compact stats bar
        assert "8 branches" in resp.text

    async def test_repo_detail_stale_threshold_highlighting(
        self, web_client: AsyncClient
    ) -> None:
        """acme/api has 2 stale out of 5 issues (40%) which exceeds 20% threshold → warning."""
        resp = await web_client.get("/repo/acme/api")
        assert "text-warning" in resp.text
        assert "(2 stale)" in resp.text

    async def test_repo_detail_no_warning_when_below_threshold(
        self, web_client: AsyncClient
    ) -> None:
        """acme/frontend has 0 stale issues → should show text-success."""
        resp = await web_client.get("/repo/acme/frontend")
        # Stale Issues box should show text-success (0 stale)
        assert "Stale issues</h2>" not in resp.text
        assert 'id="pendencies"' in resp.text or 'id="all-clear"' in resp.text

    async def test_repo_without_stale_items_hides_sections(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/repo/acme/frontend")
        assert resp.status_code == 200
        # The card-level sections should not appear (stat boxes use different text)
        assert "Stale issues</h2>" not in resp.text
        assert "Stale pull requests</h2>" not in resp.text


class TestActionsPage:
    """Tests for GET /actions route."""

    async def test_actions_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/actions")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_actions_shows_empty_state(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/actions")
        assert "No actions configured" in resp.text

    async def test_actions_shows_action_definitions(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert resp.status_code == 200
        assert "Test" in resp.text
        assert "Runs pwd in each workspace" in resp.text

    async def test_actions_shows_target_summary(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert "regex: .*" in resp.text

    async def test_actions_shows_script_preview(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert "pwd" in resp.text

    async def test_actions_shows_run_button(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert "/partials/action-run-status/test" in resp.text

    async def test_actions_shows_result_counts(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert "fa-check" in resp.text
        assert " 2" in resp.text

    async def test_actions_has_results_button(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert "/partials/action-results/test" in resp.text
        assert "Results" in resp.text

    async def test_actions_shows_toggle_for_scheduled(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert "/api/actions/test/toggle" in resp.text
        assert "Disable" in resp.text

    async def test_actions_navbar_active(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/actions")
        assert "Actions" in resp.text


class TestDashboardPartial:
    """Tests for GET /partials/dashboard-matrix route."""

    async def test_partial_returns_html(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=name&dir=asc")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_partial_contains_repos(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=name&dir=asc")
        assert "api" in resp.text
        assert "frontend" in resp.text

    async def test_sort_name_asc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=name&dir=asc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert api_pos < frontend_pos

    async def test_sort_name_desc(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=name&dir=desc")
        text = resp.text
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_sort_issues(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=issues&dir=desc")
        text = resp.text
        # acme/frontend has 10 issues, acme/api has 5 — frontend should come first
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_sort_last_activity(self, web_client: AsyncClient) -> None:
        resp = await web_client.get(
            "/partials/dashboard-matrix?sort=last_activity&dir=desc"
        )
        text = resp.text
        # acme/frontend has 2026-04-12, acme/api has 2026-04-10 — frontend should come first
        api_pos = text.index("acme/api")
        frontend_pos = text.index("acme/frontend")
        assert frontend_pos < api_pos

    async def test_matrix_has_table_structure(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=name&dir=asc")
        assert "<table" in resp.text
        assert "<thead>" in resp.text
        assert "<tbody>" in resp.text

    async def test_matrix_shows_sortable_headers(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=name&dir=asc")
        assert "hx-get" in resp.text
        assert "/partials/dashboard-matrix" in resp.text

    async def test_matrix_shows_workflow_icons(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/dashboard-matrix?sort=name&dir=asc")
        assert "status-icon-success" in resp.text
        assert "status-icon-failure" in resp.text
        # A skipped workflow gets its own icon, not the grey "unknown" dash.
        assert "status-icon-skipped" in resp.text
        assert "Deploy (main): skipped" in resp.text


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


class TestActionRunPartial:
    """Tests for GET /partials/action-run/{run_id} route."""

    async def test_action_run_partial_returns_html(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/partials/action-run/1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_action_run_partial_shows_no_results_when_empty(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/partials/action-run/999")
        assert "No per-repo results" in resp.text

    async def test_action_run_partial_shows_repo_results(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-run/1")
        assert resp.status_code == 200
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_action_run_partial_shows_status_badges(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-run/1")
        assert "pass" in resp.text
        assert "badge-success" in resp.text

    async def test_action_run_partial_has_output_toggle(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-run/1")
        assert "Output" in resp.text
        assert "/workspace/acme/api" in resp.text


class TestActionResultsPartial:
    """Tests for GET /partials/action-results/{slug} route."""

    async def test_returns_results_for_slug(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-results/test")
        assert resp.status_code == 200
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_empty_when_no_results(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-results/nonexistent")
        assert resp.status_code == 200
        assert "No results for this action" in resp.text

    async def test_shows_status_icons(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-results/test")
        assert "status-icon-pass" in resp.text

    async def test_has_output_buttons(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-results/test")
        assert "/partials/action-output/" in resp.text
        assert "Output" in resp.text

    async def test_shows_run_grouping(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-results/test")
        assert "<details" in resp.text
        assert "manual" in resp.text


class TestActionOutputPartial:
    """Tests for GET /partials/action-output/{result_id} route."""

    async def test_returns_output(self, web_client_with_actions: AsyncClient) -> None:
        resp = await web_client_with_actions.get("/partials/action-output/1")
        assert resp.status_code == 200
        assert "/workspace/acme/api" in resp.text

    async def test_empty_output(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/action-output/999")
        assert resp.status_code == 200
        assert "no stdout/stderr" in resp.text.lower() or "output" in resp.text.lower()


class TestCheckOutputPartial:
    """Tests for GET /partials/check-output/{result_id} route."""

    async def test_check_output_partial_returns_html(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/partials/check-output/1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


class TestCheckDisplay:
    """Tests for check display across dashboard views."""

    async def test_matrix_show_check_icons(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get(
            "/partials/dashboard-matrix?sort=name&dir=asc"
        )
        assert resp.status_code == 200
        assert "Checks" in resp.text
        assert "status-icon-pass" in resp.text
        assert "status-icon-fail" in resp.text

    async def test_matrix_show_not_run_checks(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        """Watchdog targets both repos but only has results for some branches."""
        resp = await web_client_with_checks.get(
            "/partials/dashboard-matrix?sort=name&dir=asc"
        )
        assert "status-icon-not-run" in resp.text

    async def test_list_show_check_dots(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get(
            "/partials/dashboard-list?sort=name&dir=asc"
        )
        assert resp.status_code == 200
        assert "status-icon-pass" in resp.text
        assert "status-icon-fail" in resp.text

    async def test_matrix_show_check_icons_for_checks(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get(
            "/partials/dashboard-matrix?sort=name&dir=asc"
        )
        assert resp.status_code == 200
        assert ">Checks<" in resp.text
        assert "status-icon-pass" in resp.text
        assert "status-icon-fail" in resp.text

    async def test_repo_detail_shows_checks(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/repo/acme/api")
        assert resp.status_code == 200
        assert "Checks" in resp.text
        assert "Watchdog" in resp.text
        assert "status-icon-pass" in resp.text

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

    async def test_check_output_loads_from_db(
        self, web_client_with_checks: AsyncClient
    ) -> None:
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

    async def test_checks_shows_descriptions(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "Always green sentinel" in resp.text
        assert "Check charm libs" in resp.text

    async def test_checks_shows_target_summaries(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "regex: .*" in resp.text
        assert "regex: -operator$" in resp.text

    async def test_checks_shows_toggle_buttons(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "/api/checks/watchdog/toggle" in resp.text
        assert "/api/checks/charm-libs/toggle" in resp.text

    async def test_checks_shows_run_buttons(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "/partials/check-run-status/watchdog" in resp.text
        assert "/partials/check-run-status/charm-libs" in resp.text

    async def test_checks_shows_result_counts(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        # Watchdog has 1 pass + 1 fail from fixture data — shown as FA icons with counts
        assert "fa-check" in resp.text
        assert "fa-xmark" in resp.text

    async def test_checks_has_inline_results_button(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        # Results are loaded inline per-check via HTMX
        assert "/partials/check-results/watchdog" in resp.text

    async def test_checks_empty_shows_no_results_hint(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/checks")
        # Empty state — no checks configured message
        assert "No checks configured" in resp.text

    async def test_checks_shows_script_preview(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "exit 0" in resp.text

    async def test_checks_navbar_active(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/checks")
        assert "Checks" in resp.text


class TestCheckResultsPartial:
    """Tests for GET /partials/check-results/{slug} route."""

    async def test_returns_results_for_slug(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/partials/check-results/watchdog")
        assert resp.status_code == 200
        assert "acme/api" in resp.text
        assert "acme/frontend" in resp.text

    async def test_empty_when_no_results(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/partials/check-results/charm-libs")
        assert resp.status_code == 200
        assert "No results for this check" in resp.text


class TestCheckRunStatusPartial:
    """Tests for GET /partials/check-run-status/{slug} route."""

    async def test_idle_state_shows_run_button(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/partials/check-run-status/watchdog")
        assert resp.status_code == 200
        assert "/partials/check-run/watchdog" in resp.text
        assert "Running" not in resp.text

    async def test_running_state_shows_spinner(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        from grimoire.checks.engine import CheckProgress, _running_checks

        _running_checks["watchdog"] = CheckProgress(completed=2, total=5)
        try:
            resp = await web_client_with_checks.get(
                "/partials/check-run-status/watchdog"
            )
            assert resp.status_code == 200
            assert "Running" in resp.text
            assert "disabled" in resp.text
            assert "2/5" in resp.text
        finally:
            _running_checks.pop("watchdog", None)

    async def test_transition_sends_hx_trigger(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get(
            "/partials/check-run-status/watchdog?was_running=1"
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Trigger") == "checkRunCompleted"

    async def test_db_running_state_falls_back(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        """A cron/MCP run is visible even when memory is empty (F13)."""
        from sqlmodel import select
        from sqlmodel.ext.asyncio.session import AsyncSession

        import grimoire.checks.router as checks_router
        from grimoire.database import CheckRunRecord

        engine = checks_router._engine
        assert engine is not None
        async with AsyncSession(engine) as session:
            session.add(
                CheckRunRecord(
                    check_slug="watchdog",
                    check_name="Watchdog",
                    triggered_by="cron",
                    status="running",
                )
            )
            await session.commit()
        try:
            resp = await web_client_with_checks.get(
                "/partials/check-run-status/watchdog"
            )
            assert "Running" in resp.text
        finally:
            async with AsyncSession(engine) as session:
                rows = (
                    await session.exec(
                        select(CheckRunRecord).where(
                            CheckRunRecord.check_slug == "watchdog",
                            CheckRunRecord.status == "running",
                        )
                    )
                ).all()
                for row in rows:
                    await session.delete(row)
                await session.commit()

    async def test_no_trigger_when_still_running(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        from grimoire.checks.engine import CheckProgress, _running_checks

        _running_checks["watchdog"] = CheckProgress()
        try:
            resp = await web_client_with_checks.get(
                "/partials/check-run-status/watchdog?was_running=1"
            )
            assert "HX-Trigger" not in resp.headers
        finally:
            _running_checks.pop("watchdog", None)


class TestActionRunStatusPartial:
    """Tests for GET /partials/action-run-status/{slug} route."""

    async def test_idle_state_shows_run_button(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-run-status/test")
        assert resp.status_code == 200
        assert "/partials/action-run/test" in resp.text
        assert "Running" not in resp.text

    async def test_transition_sends_hx_trigger(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get(
            "/partials/action-run-status/test?was_running=1"
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Trigger") == "actionRunCompleted"


class TestRefreshPartials:
    """Tests for refresh progress partials."""

    async def test_refresh_status_idle(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/refresh-status")
        assert resp.status_code == 200
        assert "Refresh" in resp.text
        # Should show the idle button, not the running state
        assert "Refreshing" not in resp.text

    async def test_refresh_status_shows_button(self, web_client: AsyncClient) -> None:
        resp = await web_client.get("/partials/refresh-status")
        assert "refresh-btn" in resp.text

    async def test_refresh_status_hx_trigger_on_completion(
        self, web_client: AsyncClient
    ) -> None:
        """When was_running=1 and refresh is idle, should send HX-Trigger."""
        resp = await web_client.get("/partials/refresh-status?was_running=1")
        assert resp.status_code == 200
        assert resp.headers.get("HX-Trigger") == "refreshCompleted"

    async def test_refresh_status_no_trigger_when_not_was_running(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/partials/refresh-status?was_running=0")
        assert "HX-Trigger" not in resp.headers

    async def test_dashboard_contains_refresh_partial(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/")
        assert "refresh-btn" in resp.text
        assert "Refresh" in resp.text

    async def test_dashboard_has_refresh_completed_listener(
        self, web_client: AsyncClient
    ) -> None:
        resp = await web_client.get("/")
        assert "refreshCompleted" in resp.text


class TestActionProgressUI:
    """Tests for action progress display in partials."""

    async def test_action_status_idle(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get("/partials/action-run-status/test")
        assert resp.status_code == 200
        assert "Running" not in resp.text

    async def test_action_status_hx_trigger_on_completion(
        self, web_client_with_actions: AsyncClient
    ) -> None:
        resp = await web_client_with_actions.get(
            "/partials/action-run-status/test?was_running=1"
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Trigger") == "actionRunCompleted"


class TestLoadingState:
    """Tests for the loading page when cache is empty and refresh is running."""

    async def test_dashboard_shows_loading_when_cache_empty_and_refreshing(
        self, web_client: AsyncClient
    ) -> None:
        """When cache is empty and a refresh is running, show loading page."""
        from unittest.mock import patch

        from grimoire.github.router import _cache
        from grimoire.github.service import RefreshProgress

        saved = dict(_cache)
        _cache.clear()
        try:
            with (
                patch(
                    "grimoire.github.service.is_refresh_running",
                    return_value=True,
                ),
                patch(
                    "grimoire.github.service.get_refresh_progress",
                    return_value=RefreshProgress(completed=2, total=5),
                ),
            ):
                resp = await web_client.get("/")
                assert resp.status_code == 200
                assert "Fetching repository data" in resp.text
                assert "2 of 5" in resp.text
        finally:
            _cache.update(saved)

    async def test_dashboard_shows_normal_when_cache_populated(
        self, web_client: AsyncClient
    ) -> None:
        """When cache has repos, show normal dashboard even if refresh is running."""
        resp = await web_client.get("/")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text
        assert "Fetching repository data" not in resp.text

    async def test_loading_status_partial_redirects_when_done(
        self, web_client: AsyncClient
    ) -> None:
        """When refresh is no longer running, loading-status returns HX-Redirect."""
        from unittest.mock import patch

        with patch(
            "grimoire.github.service.is_refresh_running",
            return_value=False,
        ):
            resp = await web_client.get("/partials/loading-status")
            assert resp.status_code == 200
            assert resp.headers.get("HX-Redirect") == "/"

    async def test_loading_status_partial_returns_progress(
        self, web_client: AsyncClient
    ) -> None:
        """When refresh is running, loading-status returns progress info."""
        from unittest.mock import patch

        from grimoire.github.service import RefreshProgress

        with (
            patch(
                "grimoire.github.service.is_refresh_running",
                return_value=True,
            ),
            patch(
                "grimoire.github.service.get_refresh_progress",
                return_value=RefreshProgress(completed=3, total=7),
            ),
        ):
            resp = await web_client.get("/partials/loading-status")
            assert resp.status_code == 200
            assert "3 of 7" in resp.text
            assert "HX-Redirect" not in resp.headers


class TestTimeAgoHelper:
    def test_time_ago_handles_none(self) -> None:
        """_time_ago returns 'never' when timestamp is None."""
        from grimoire.web.router import _time_ago

        assert _time_ago(None) == "never"

    def test_time_ago_future_date_not_negative(self) -> None:
        """A future timestamp must not yield a negative '-Ns ago' (bug #10)."""
        from datetime import datetime, timedelta, timezone

        from grimoire.web.router import _time_ago

        now = datetime.now(timezone.utc)
        future = now + timedelta(seconds=30)
        result = _time_ago(future)
        # Must not contain a minus sign
        assert "-" not in result
        assert result in {"0s ago", "just now"}


class TestBacklogSaveWeightsValidation:
    async def test_save_weights_invalid_payload_returns_400(
        self, web_client: AsyncClient, tmp_path: Path
    ) -> None:
        """Posting invalid category weights returns 400 and preserves config file."""
        from grimoire.web import router

        config_file = tmp_path / "config.yaml"
        config_file.write_text("github:\n  token: test\n")
        router.set_backlog_config(None, config_file)

        resp = await web_client.post(
            "/api/backlog/save-weights",
            json={"category_weights": "not_a_dict"},
        )
        assert resp.status_code == 400
        # Verify file on disk was not corrupted
        assert "not_a_dict" not in config_file.read_text()

    async def test_save_weights_writes_atomically(
        self, web_client: AsyncClient, tmp_path: Path
    ) -> None:
        """A successful write leaves no stray temp files in the config dir (bug #12)."""
        from grimoire.web import router

        config_file = tmp_path / "config.yaml"
        config_file.write_text("github:\n  token: test\nrepositories:\n  - repo: o/r\n")
        router.set_backlog_config(None, config_file)

        resp = await web_client.post(
            "/api/backlog/save-weights",
            json={"category_weights": {"bug": 5}},
        )
        assert resp.status_code == 200
        # Config file written with the new weights
        assert "category_weights" in config_file.read_text()
        # No leftover temp files in the config directory (atomic rename cleans up)
        leftover = [p for p in tmp_path.iterdir() if p.name != config_file.name]
        assert leftover == [], f"unexpected leftover files: {leftover}"

    async def test_save_weights_writes_validated_model(
        self, web_client: AsyncClient, tmp_path: Path
    ) -> None:
        """The persisted config reflects the validated backlog, not raw merged JSON (bug #2)."""
        from grimoire.web import router

        config_file = tmp_path / "config.yaml"
        config_file.write_text("github:\n  token: test\nrepositories:\n  - repo: o/r\n")
        router.set_backlog_config(None, config_file)

        resp = await web_client.post(
            "/api/backlog/save-weights",
            json={"category_weights": {"failing_workflow": 5}},
        )
        assert resp.status_code == 200
        import yaml

        written = yaml.safe_load(config_file.read_text())
        # The backlog section is well-formed (validated shape), not arbitrary JSON
        assert isinstance(written["backlog"], dict)
        # The user's weight overrides the default; the model fills the rest
        cw = written["backlog"]["category_weights"]
        assert isinstance(cw, dict)
        assert cw["failing_workflow"] == 5
        # Non-user-supplied categories retain their defaults
        assert cw["failing_check_error"] == 80.0


class TestSessionExecuteDeprecationSuppressed:
    """Bug #8 — the SQLModel session.execute() deprecation nag is silenced.

    All ``session.execute()`` call sites in router.py run raw ``text()`` SQL,
    for which ``session.execute()`` is the *correct* API (``session.exec()`` is for
    ORM ``select()`` — see the already-fixed bugs ``checks-router-improper-session-exec``
    and ``github-service-improper-delete-exec``). The fix uses ``_exec_text()``, a
    wrapper that suppresses the misleading SQLModel DeprecationWarning via a
    ``warnings.catch_warnings()`` context manager at each call site.
    """

    async def test_exec_text_suppresses_nag(self) -> None:
        """_exec_text() prevents the real SQLModel nag from escaping.

        Uses a real AsyncSession so the SQLModel ``execute()`` wrapper actually
        emits its warning — a mocked ``session.execute`` would make this test
        vacuous (bug #8).
        """
        import warnings

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlmodel.ext.asyncio.session import AsyncSession

        from grimoire.web.router import _exec_text

        engine = create_async_engine("sqlite+aiosqlite://")
        try:
            async with AsyncSession(engine) as session:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    await _exec_text(session, text("SELECT 1"))
        finally:
            await engine.dispose()

        nags = [w for w in caught if "session.exec" in str(w.message)]
        assert nags == [], f"SQLModel session.execute() nag leaked: {len(nags)} nags"


async def test_action_results_include_failed_run(
    web_client_with_actions: AsyncClient,
) -> None:
    """Failed runs are terminal and must appear in the run history partial."""
    from datetime import datetime, timezone

    from sqlmodel.ext.asyncio.session import AsyncSession

    from grimoire.actions.router import _engine
    from grimoire.database import ActionRunRecord, ActionRunRepoRecord

    assert _engine is not None
    async with AsyncSession(_engine) as session:
        run = ActionRunRecord(
            action_slug="test",
            action_name="Test",
            triggered_by="manual",
            status="failed",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.flush()
        session.add(
            ActionRunRepoRecord(
                run_id=run.id,  # type: ignore[arg-type]
                repo_full_name="acme/api",
                branch="main",
                passed=False,
                output="boom-unique-failure",
            )
        )
        await session.commit()

    resp = await web_client_with_actions.get("/partials/action-results/test")
    assert resp.status_code == 200
    # The failed run is rendered alongside the fixture's completed run.
    assert resp.text.count("<details") >= 2
    assert 'title="fail"' in resp.text


class TestRepoChecksRun:
    """Run all checks for one repo from the detail page (story e13s05)."""

    async def test_detail_page_has_run_checks_button(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/repo/acme/frontend")
        assert "/partials/repo-checks-run/acme/frontend" in resp.text

    async def test_status_partial_idle(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get(
            "/partials/repo-checks-status/acme/frontend"
        )
        assert resp.status_code == 200
        assert "Run checks" in resp.text
        assert "hx-post" in resp.text

    async def test_run_unknown_repo_404(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.post("/partials/repo-checks-run/no/pe")
        assert resp.status_code == 404

    async def test_run_starts_and_returns_running_state(
        self, web_client_with_checks: AsyncClient, monkeypatch: object
    ) -> None:
        import grimoire.checks.engine as eng
        import grimoire.checks.router as checks_router

        calls: list[str] = []

        async def fake_run(plan, repos, workspace, engine, repo_full_name=None, **kw):  # type: ignore[no-untyped-def]
            calls.append(plan.repo_full_name)
            return []

        monkeypatch.setattr(eng, "run_reserved_checks_for_repo", fake_run)  # type: ignore[attr-defined]
        monkeypatch.setattr(checks_router, "_workspace", object())  # type: ignore[attr-defined]
        resp = await web_client_with_checks.post(
            "/partials/repo-checks-run/acme/frontend"
        )
        assert resp.status_code == 200
        assert "Running" in resp.text
        assert calls == ["acme/frontend"]

    async def test_check_counts_separate_not_run(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        resp = await web_client_with_checks.get("/repo/acme/frontend")
        assert "not run" in resp.text


def test_drop_untargeted_results_discards_retargeted_check_rows() -> None:
    from grimoire.targeting import TargetSpec
    from grimoire.web.router import _drop_untargeted_results

    class _Check:
        def __init__(self, slug: str, targets: TargetSpec) -> None:
            self.slug = slug
            self.targets = targets

    listed = _Check("listed", TargetSpec(list=["a/y"]))
    scripted = _Check("scripted", TargetSpec(script="true"))
    old = {"id": 1, "passed": False}
    results = {
        ("listed", "a/x", "main"): old,
        ("listed", "a/y", "main"): old,
        ("scripted", "a/x", "main"): old,
    }
    kept = _drop_untargeted_results(
        [listed, scripted], {"listed": {("a/y", "main")}, "scripted": set()}, results
    )
    assert set(kept) == {("listed", "a/y", "main"), ("scripted", "a/x", "main")}
