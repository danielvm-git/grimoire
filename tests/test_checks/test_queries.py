# story: e12s01
"""Unit tests for CheckQueryService (get_latest_check_results and get_check_backlog)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.checks.loader import CheckDefinition
from grimoire.checks.queries import get_check_backlog, get_latest_check_results
from grimoire.database import CheckResultRecord, create_tables, get_engine
from grimoire.targeting import TargetSpec


def _make_check(slug: str = "lint", name: str = "Linting") -> CheckDefinition:
    return CheckDefinition(
        slug=slug,
        name=name,
        description="Run linter",
        severity="error",
        targets=TargetSpec(list=["acme/repo1"]),
        script="exit 0",
        file_path=Path(f"/tmp/{slug}.yaml"),
    )


@pytest.mark.asyncio
async def test_get_latest_check_results_multi_repo(tmp_path: Path) -> None:
    db_engine = await get_engine(str(tmp_path / "test_queries.db"))
    await create_tables(db_engine)

    ts1 = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)

    async with AsyncSession(db_engine) as session:
        # Older result for repo1
        session.add(
            CheckResultRecord(
                check_slug="lint",
                check_name="Linting",
                repo_full_name="acme/repo1",
                branch="main",
                passed=False,
                timestamp=ts1,
                output="Old error",
            )
        )
        # Newer result for repo1 (should be selected)
        session.add(
            CheckResultRecord(
                check_slug="lint",
                check_name="Linting",
                repo_full_name="acme/repo1",
                branch="main",
                passed=True,
                timestamp=ts2,
                output="All clean",
            )
        )
        # Result for repo2
        session.add(
            CheckResultRecord(
                check_slug="security",
                check_name="Security Scan",
                repo_full_name="acme/repo2",
                branch="main",
                passed=False,
                timestamp=ts2,
                output="Vulnerability found",
            )
        )
        await session.commit()

    async with AsyncSession(db_engine) as session:
        # Test query without repo filter (fetches all repos)
        all_results = await get_latest_check_results(session)
        assert len(all_results) == 2
        slugs = {r.check_slug for r in all_results}
        assert slugs == {"lint", "security"}

        # Verify only latest for repo1 was returned
        repo1_res = [r for r in all_results if r.repo_full_name == "acme/repo1"][0]
        assert repo1_res.passed is True
        assert repo1_res.output == "All clean"

        # Test query with repo filter
        repo2_results = await get_latest_check_results(
            session, repo_full_name="acme/repo2"
        )
        assert len(repo2_results) == 1
        assert repo2_results[0].check_slug == "security"
        assert repo2_results[0].passed is False


@pytest.mark.asyncio
async def test_get_check_backlog_comprehensive(tmp_path: Path) -> None:
    db_engine = await get_engine(str(tmp_path / "test_backlog.db"))
    await create_tables(db_engine)

    ts = datetime(2026, 11, 5, 10, 0, 0, tzinfo=timezone.utc)
    large_output = "E" * 70000

    async with AsyncSession(db_engine) as session:
        # Passing check
        session.add(
            CheckResultRecord(
                check_slug="fmt",
                check_name="Format",
                repo_full_name="acme/repo1",
                branch="main",
                passed=True,
                timestamp=ts,
                output="Formatted OK",
            )
        )
        # Failing check with large output snippet
        session.add(
            CheckResultRecord(
                check_slug="lint",
                check_name="Lint",
                repo_full_name="acme/repo1",
                branch="main",
                passed=False,
                timestamp=ts,
                output=large_output,
            )
        )
        await session.commit()

    fmt_def = _make_check("fmt", "Format")
    lint_def = _make_check("lint", "Lint")
    unexecuted_def = _make_check("audit", "Audit")

    async with AsyncSession(db_engine) as session:
        backlog = await get_check_backlog(
            session=session,
            repo_full_name="acme/repo1",
            check_definitions=[fmt_def, lint_def, unexecuted_def],
        )

        assert backlog["repository"] == "acme/repo1"
        assert backlog["all_passed"] is False
        assert backlog["summary"]["total_checks"] == 3
        assert backlog["summary"]["passing"] == 1
        assert backlog["summary"]["failing"] == 1
        assert backlog["summary"]["unexecuted"] == 1

        # Check passing list
        assert len(backlog["passing_checks"]) == 1
        assert backlog["passing_checks"][0]["slug"] == "fmt"
        assert backlog["passing_checks"][0]["output"] == "Formatted OK"

        # Check failing list & log truncation
        assert len(backlog["failing_checks"]) == 1
        assert backlog["failing_checks"][0]["slug"] == "lint"
        assert len(backlog["failing_checks"][0]["output"]) == 65536

        # Check unexecuted list
        assert len(backlog["unexecuted_checks"]) == 1
        assert backlog["unexecuted_checks"][0]["slug"] == "audit"
        assert backlog["unexecuted_checks"][0]["status"] == "unexecuted"

        # Edge case: check_definitions is None
        empty_backlog = await get_check_backlog(
            session=session,
            repo_full_name="acme/repo1",
            check_definitions=None,
        )
        assert empty_backlog["all_passed"] is True
        assert empty_backlog["summary"]["total_checks"] == 0
