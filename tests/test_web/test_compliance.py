"""Per-repo pattern compliance score."""

from __future__ import annotations

from typing import Any

from grimoire.web.compliance import compute_compliance


def _e(priority: str | None, status: str) -> dict[str, Any]:
    return {"priority": priority, "status": status}


class TestComputeCompliance:
    def test_none_without_pattern_checks(self) -> None:
        assert compute_compliance({"main": [_e(None, "fail")]}) is None

    def test_counts_p0_and_p1(self) -> None:
        c = compute_compliance(
            {
                "main": [
                    _e("P0", "pass"),
                    _e("P0", "fail"),
                    _e("P1", "pass"),
                    _e("P1", "pass"),
                ]
            }
        )
        assert c is not None
        assert (c.p0_passed, c.p0_total, c.p1_passed, c.p1_total) == (1, 2, 2, 2)
        assert c.percent == 75
        assert c.tier == "fail"
        assert c.p0_failing == 1

    def test_p1_failure_is_partial(self) -> None:
        c = compute_compliance({"main": [_e("P0", "pass"), _e("P1", "fail")]})
        assert c is not None and c.tier == "partial" and c.percent == 50

    def test_all_pass(self) -> None:
        c = compute_compliance({"main": [_e("P0", "pass"), _e("P1", "pass")]})
        assert c is not None and c.tier == "pass" and c.percent == 100

    def test_not_run_is_never_counted_as_passing(self) -> None:
        c = compute_compliance({"main": [_e("P0", "not-run"), _e("P1", "pass")]})
        assert c is not None
        assert c.not_run == 1
        assert (c.p0_total, c.percent) == (0, 100)

    def test_nothing_ran_has_no_percent(self) -> None:
        c = compute_compliance({"main": [_e("P0", "not-run")]})
        assert c is not None and c.percent is None

    def test_p2_is_ignored(self) -> None:
        assert compute_compliance({"main": [_e("P2", "fail")]}) is None


# --- Routes ---------------------------------------------------------------

from collections.abc import AsyncIterator  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from grimoire.app import create_app  # noqa: E402
from grimoire.checks.loader import CheckDefinition  # noqa: E402
from grimoire.database import (  # noqa: E402
    CheckResultRecord,
    CheckRunRecord,
    create_tables,
    get_engine,
)
from grimoire.targeting import TargetSpec  # noqa: E402
from tests.test_web.conftest import _populate_cache  # noqa: E402

_TS = datetime(2026, 11, 8, tzinfo=timezone.utc)


@pytest.fixture
async def pattern_client(tmp_path: object) -> AsyncIterator[AsyncClient]:
    """acme/api: P0 pass + P1 fail (50%). acme/frontend: P0 fail on main (0%)."""
    import grimoire.checks.router as checks_router
    from grimoire.actions.router import _actions

    saved_actions, saved_checks = _actions[:], checks_router._checks[:]
    saved_engine = checks_router._engine
    _actions.clear()
    checks_router._checks.clear()
    _populate_cache()

    engine = await get_engine(str(tmp_path) + "/compliance.db")  # type: ignore[arg-type]
    await create_tables(engine)
    p0 = CheckDefinition(
        name="Agent context symlinks",
        slug="agent-context-symlinks",
        description="d",
        targets=TargetSpec(regex=".*"),
        script="true",
        severity="error",
        priority="P0",
    )
    p1 = CheckDefinition(
        name="CONVENTIONS.md present",
        slug="conventions-md",
        description="d",
        targets=TargetSpec(regex=".*"),
        script="true",
        severity="warning",
        priority="P1",
    )
    checks_router._checks.extend([p0, p1])
    checks_router._engine = engine

    rows = [
        ("agent-context-symlinks", "acme/api", True),
        ("conventions-md", "acme/api", False),
        ("agent-context-symlinks", "acme/frontend", False),
    ]
    async with AsyncSession(engine) as session:
        for slug, repo, passed in rows:
            run = CheckRunRecord(
                check_slug=slug,
                check_name=slug,
                triggered_by="manual",
                status="completed",
                started_at=_TS,
                finished_at=_TS,
            )
            session.add(run)
            await session.flush()
            session.add(
                CheckResultRecord(
                    run_id=run.id,
                    check_slug=slug,
                    check_name=slug,
                    repo_full_name=repo,
                    branch="main",
                    passed=passed,
                    output="",
                    timestamp=_TS,
                )
            )
        await session.commit()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    _actions.clear()
    _actions.extend(saved_actions)
    checks_router._checks.clear()
    checks_router._checks.extend(saved_checks)
    checks_router._engine = saved_engine
    await engine.dispose()


class TestComplianceRoutes:
    async def test_repo_page_shows_breakdown(self, pattern_client: AsyncClient) -> None:
        html = (await pattern_client.get("/repo/acme/api")).text
        assert 'id="compliance-summary"' in html
        assert "P0 1/1" in html
        assert "P1 0/1" in html
        assert "50%" in html

    async def test_matrix_has_sortable_column(
        self, pattern_client: AsyncClient
    ) -> None:
        resp = await pattern_client.get(
            "/partials/dashboard-matrix?sort=compliance&dir=asc"
        )
        assert resp.status_code == 200
        html = resp.text
        assert "Compliance" in html
        # Ascending: frontend (0%) before api (50%).
        assert html.index("acme/frontend") < html.index('acme/api"')

    async def test_repo_without_pattern_checks_has_no_summary(
        self, web_client_with_checks: AsyncClient
    ) -> None:
        html = (await web_client_with_checks.get("/repo/acme/api")).text
        assert 'id="compliance-summary"' not in html
