"""Tests for check definition loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from grimoire.checks.loader import load_checks


class TestLoadChecks:
    def test_valid_yaml(self, tmp_path: Path) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        (checks_dir / "uv-lock-fresh.yaml").write_text(
            "name: UV Lock Fresh\n"
            "description: Ensures uv.lock is fresh\n"
            "targets:\n"
            "  regex: 'acme/.*'\n"
            "script: uv lock --check\n"
            "schedule: '0 */6 * * *'\n"
            "enabled: true\n"
        )

        checks = load_checks(tmp_path)
        assert len(checks) == 1
        c = checks[0]
        assert c.name == "UV Lock Fresh"
        assert c.slug == "uv-lock-fresh"
        assert c.description == "Ensures uv.lock is fresh"
        assert c.targets.regex == "acme/.*"
        assert c.script == "uv lock --check"
        assert c.schedule == "0 */6 * * *"
        assert c.enabled is True

    def test_slug_derived_from_filename(self, tmp_path: Path) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        (checks_dir / "my-cool-check.yaml").write_text(
            "name: My Cool Check\n"
            "description: Does stuff\n"
            "targets:\n"
            "  list:\n"
            "    - acme/alpha\n"
            "script: echo ok\n"
        )

        checks = load_checks(tmp_path)
        assert checks[0].slug == "my-cool-check"

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        (checks_dir / "bad.yaml").write_text(
            "name: Bad Check\n# missing description, targets, script\n"
        )

        with pytest.raises(Exception):
            load_checks(tmp_path)

    def test_empty_directory(self, tmp_path: Path) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        assert load_checks(tmp_path) == []

    def test_missing_directory(self, tmp_path: Path) -> None:
        assert load_checks(tmp_path) == []

    def test_optional_schedule_defaults_none(self, tmp_path: Path) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        (checks_dir / "simple.yaml").write_text(
            "name: Simple\n"
            "description: A simple check\n"
            "targets:\n"
            "  list:\n"
            "    - acme/repo\n"
            "script: echo 1\n"
        )
        checks = load_checks(tmp_path)
        assert checks[0].schedule is None
        assert checks[0].enabled is True

    def test_multiple_checks_sorted(self, tmp_path: Path) -> None:
        checks_dir = tmp_path / "checks"
        checks_dir.mkdir()
        for name in ("beta-check.yaml", "alpha-check.yaml"):
            (checks_dir / name).write_text(
                f"name: {name}\ndescription: test\ntargets:\n  list:\n    - a/b\nscript: echo ok\n"
            )
        checks = load_checks(tmp_path)
        assert [c.slug for c in checks] == ["alpha-check", "beta-check"]
