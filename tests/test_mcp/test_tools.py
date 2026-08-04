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
