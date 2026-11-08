# story: e12s02
"""Unit tests for MCP tool handlers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from grimoire.checks.loader import CheckDefinition
from grimoire.database import CheckResultRecord, create_tables, get_engine
from grimoire.mcp.tools import MCPToolHandlers, validate_check_slug, validate_repo
from grimoire.models import TrackedRepository
from grimoire.targeting import TargetSpec
from grimoire.workspace.manager import WorkspaceManager


def _check(slug: str = "lint", name: str = "Linting") -> CheckDefinition:
    return CheckDefinition(
        slug=slug,
        name=name,
        description="Run linter",
        severity="error",
        targets=TargetSpec(list=["lucabello/grimoire"]),
        script="exit 0",
        file_path=Path(f"/tmp/{slug}.yaml"),
    )


def _repo(full_name: str = "lucabello/grimoire") -> TrackedRepository:
    return TrackedRepository(
        full_name=full_name,
        default_branch="main",
        branches=["main"],
    )


def _workspace(tmp_path: Path) -> WorkspaceManager:
    mock_config = MagicMock()
    mock_config.workspace_dir = tmp_path / "workspace"
    return WorkspaceManager(config=mock_config)


@pytest.mark.asyncio
async def test_validate_repo_and_slug():
    validate_repo("lucabello/grimoire")
    with pytest.raises(ValueError, match="Invalid repository format"):
        validate_repo("invalid_repo")

    validate_check_slug("lint_check-1")
    with pytest.raises(ValueError, match="Invalid check slug format"):
        validate_check_slug("lint; rm -rf /")


@pytest.mark.asyncio
async def test_mcp_tool_list_repositories(tmp_path: Path):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo("lucabello/grimoire")],
        workspace=wm,
    )

    repos = await handlers.list_repositories()
    assert len(repos) == 1
    assert repos[0]["full_name"] == "lucabello/grimoire"


@pytest.mark.asyncio
async def test_mcp_tool_list_checks(tmp_path: Path):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check("test-check", "Test Check")],
        repos=[_repo()],
        workspace=wm,
    )

    checks = await handlers.list_checks()
    assert len(checks) == 1
    assert checks[0]["slug"] == "test-check"
    assert checks[0]["name"] == "Test Check"


@pytest.mark.asyncio
async def test_mcp_tool_get_repo_checks_status_and_backlog(tmp_path: Path):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    # Seed check result in DB
    async with AsyncSession(db_engine) as session:
        session.add(
            CheckResultRecord(
                check_slug="lint",
                check_name="Linting",
                repo_full_name="lucabello/grimoire",
                branch="main",
                passed=False,
                output="Syntax error in line 42",
            )
        )
        await session.commit()

    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check("lint", "Linting")],
        repos=[_repo("lucabello/grimoire")],
        workspace=wm,
    )

    status = await handlers.get_repo_checks_status("lucabello/grimoire")
    assert status["overall_status"] == "failing"
    assert status["failing"] == 1

    backlog = await handlers.get_check_backlog_data("lucabello/grimoire")
    assert backlog["all_passed"] is False
    assert len(backlog["failing_checks"]) == 1
    assert backlog["failing_checks"][0]["slug"] == "lint"
    assert "Syntax error" in backlog["failing_checks"][0]["output"]


@pytest.mark.asyncio
async def test_mcp_tool_refresh_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check("lint", "Linting")],
        repos=[_repo("lucabello/grimoire")],
        workspace=wm,
    )

    # 1. Test refresh in get_repo_checks_status with CheckConflictError handling
    conflict_called = False

    async def mock_run_conflict(*args, **kwargs):
        nonlocal conflict_called
        conflict_called = True
        from grimoire.checks.engine import CheckConflictError

        raise CheckConflictError("conflict")

    monkeypatch.setattr(
        "grimoire.mcp.tools.run_check_for_all_targets", mock_run_conflict
    )

    status = await handlers.get_repo_checks_status("lucabello/grimoire", refresh=True)
    assert conflict_called is True
    assert status["repository"] == "lucabello/grimoire"

    # 2. Test refresh in get_check_backlog_data with CheckConflictError handling
    conflict_backlog_called = False

    async def mock_run_backlog_conflict(*args, **kwargs):
        nonlocal conflict_backlog_called
        conflict_backlog_called = True
        from grimoire.checks.engine import CheckConflictError

        raise CheckConflictError("conflict")

    monkeypatch.setattr(
        "grimoire.mcp.tools.run_check_for_all_targets", mock_run_backlog_conflict
    )

    backlog = await handlers.get_check_backlog_data("lucabello/grimoire", refresh=True)
    assert conflict_backlog_called is True
    assert backlog["repository"] == "lucabello/grimoire"


@pytest.mark.asyncio
async def test_mcp_tool_run_repo_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    wm = _workspace(tmp_path)

    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check("lint", "Linting"), _check("sec", "Security")],
        repos=[_repo("lucabello/grimoire")],
        workspace=wm,
    )

    from datetime import datetime, timezone

    from grimoire.models import CheckResult

    # 1. Normal run all checks
    async def mock_run_success(*args, **kwargs):
        return [
            CheckResult(
                check_name="Linting",
                check_slug="lint",
                repo_full_name="lucabello/grimoire",
                branch="main",
                passed=True,
                output="All clean",
                timestamp=datetime.now(timezone.utc),
            )
        ]

    monkeypatch.setattr(
        "grimoire.mcp.tools.run_check_for_all_targets", mock_run_success
    )

    run_all = await handlers.run_repo_checks("lucabello/grimoire")
    assert run_all["repository"] == "lucabello/grimoire"
    assert run_all["executed_checks_count"] == 2
    assert run_all["details"][0]["passed"] is True

    # 2. Specific valid check_slug
    run_specific = await handlers.run_repo_checks(
        "lucabello/grimoire", check_slug="lint"
    )
    assert run_specific["executed_checks_count"] == 1
    assert run_specific["details"][0]["check_slug"] == "lint"

    # 3. Specific unknown check_slug -> ValueError
    with pytest.raises(ValueError, match="Check with slug 'unknown' not found"):
        await handlers.run_repo_checks("lucabello/grimoire", check_slug="unknown")

    # 4. CheckConflictError handling during run_repo_checks
    async def mock_run_conflict(*args, **kwargs):
        from grimoire.checks.engine import CheckConflictError

        raise CheckConflictError("check busy")

    monkeypatch.setattr(
        "grimoire.mcp.tools.run_check_for_all_targets", mock_run_conflict
    )

    run_conflict = await handlers.run_repo_checks(
        "lucabello/grimoire", check_slug="lint"
    )
    assert run_conflict["executed_checks_count"] == 1
    assert run_conflict["details"][0]["passed"] is False
    assert run_conflict["details"][0]["error"] == "already running"


@pytest.mark.asyncio
async def test_run_repo_checks_rejects_untracked_repository(tmp_path: Path) -> None:
    """A repo that is not tracked must be an error, never a vacuous pass.

    Regression for specs/bugs/registry.yaml mcp-tools-report-vacuous-success:
    ChecksEngine filtered specific_repo down to an empty target list and the tool
    answered {"results_count": 0, "passed": true} for a repository it never touched.
    """
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo("lucabello/grimoire")],
        workspace=_workspace(tmp_path),
    )

    with pytest.raises(ValueError, match="acme/not-tracked.*lucabello/grimoire"):
        await handlers.run_repo_checks("acme/not-tracked")

    await db_engine.dispose()


@pytest.mark.asyncio
async def test_get_repo_checks_status_rejects_untracked_repository(
    tmp_path: Path,
) -> None:
    """Status queries for an untracked repo are an error, not a silent "unknown"."""
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo("lucabello/grimoire")],
        workspace=_workspace(tmp_path),
    )

    with pytest.raises(ValueError, match="not tracked"):
        await handlers.get_repo_checks_status("acme/not-tracked")

    await db_engine.dispose()


@pytest.mark.asyncio
async def test_run_repo_checks_reports_check_without_matching_targets(
    tmp_path: Path,
) -> None:
    """A tracked repo outside a check's targets must report a failure, not a pass."""
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    # The check targets a different repository, so it resolves zero targets here.
    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo("lucabello/other")],
        workspace=_workspace(tmp_path),
    )

    result = await handlers.run_repo_checks("lucabello/other")

    detail = result["details"][0]
    assert detail["results_count"] == 0
    assert detail["passed"] is False
    assert "resolved no targets" in detail["error"]

    await db_engine.dispose()


@pytest.mark.asyncio
async def test_list_checks_includes_targets(tmp_path: Path) -> None:
    """list_checks must expose targets so an agent knows a check's scope.

    Regression for specs/bugs/registry.yaml mcp-list-checks-missing-targets:
    docs/specs/08-mcp-server.md requires slug, name, description, severity and targets.
    """
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check()],
        repos=[_repo("lucabello/grimoire")],
        workspace=_workspace(tmp_path),
    )

    checks = await handlers.list_checks()

    assert checks == [
        {
            "slug": "lint",
            "name": "Linting",
            "description": "Run linter",
            "severity": "error",
            "targets": {"list": ["lucabello/grimoire"], "regex": None, "script": None},
        }
    ]

    await db_engine.dispose()


@pytest.mark.asyncio
async def test_run_repo_checks_skips_disabled_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_engine = await get_engine(str(tmp_path / "test.db"))
    await create_tables(db_engine)
    disabled = _check("sec", "Security")
    disabled.enabled = False
    handlers = MCPToolHandlers(
        engine=db_engine,
        checks=[_check("lint", "Linting"), disabled],
        repos=[_repo()],
        workspace=_workspace(tmp_path),
    )
    ran: list[str] = []

    async def fake_run(*args, **kwargs):
        ran.append(kwargs["check"].slug)
        return []

    monkeypatch.setattr("grimoire.mcp.tools.run_check_for_all_targets", fake_run)

    await handlers.run_repo_checks("lucabello/grimoire")
    await handlers.get_repo_checks_status("lucabello/grimoire", refresh=True)
    assert set(ran) == {"lint"}

    with pytest.raises(ValueError, match="not found or disabled"):
        await handlers.run_repo_checks("lucabello/grimoire", check_slug="sec")
