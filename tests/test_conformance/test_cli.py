"""CLI contract: exit 0 only on a real pass; crashes and failures exit 1."""

from __future__ import annotations

from pathlib import Path

import pytest

from grimoire.checks.loader import load_checks
from grimoire.conformance import get_rules
from grimoire.conformance.__main__ import main
from tests.test_conformance.conftest import RepoFactory

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def test_pass_exits_zero(repo: RepoFactory, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["agent-context-symlinks", "--path", str(repo.root)]) == 0
    assert "PASS agent-context-symlinks" in capsys.readouterr().out


def test_failure_exits_one_and_lists_problems(
    repo: RepoFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    repo.remove("CLAUDE.md")
    assert main(["agent-context-symlinks", "--path", str(repo.root)]) == 1
    out = capsys.readouterr().out
    assert "FAIL agent-context-symlinks: 1 problem(s)" in out
    assert "CLAUDE.md is missing" in out


def test_crash_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Not a git repo: the history rule raises, and the CLI must report a failure.
    assert main(["conventional-commits", "--path", str(tmp_path)]) == 1
    assert "rule crashed" in capsys.readouterr().out


def test_every_rule_has_a_bundled_check() -> None:
    checks = {c.slug: c for c in load_checks(DATA_DIR)}
    for slug in get_rules():
        assert slug in checks, f"no data/checks/{slug}.yaml"
        # The interpreter comes from the environment: bare python3 is not on the
        # PATH of deployments that start uvicorn directly (run.sh).
        assert f"-m grimoire.conformance {slug}" in checks[slug].script
        assert "GRIMOIRE_PYTHON" in checks[slug].script
        assert checks[slug].priority in ("P0", "P1")
