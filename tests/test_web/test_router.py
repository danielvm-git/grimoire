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
