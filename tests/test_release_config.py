"""Release automation contract tests (big-release guide)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def test_big_release_config_is_canonical() -> None:
    """`.big-release.yml` follows the big-release guide's schema."""
    config = _load_yaml(REPO_ROOT / ".big-release.yml")

    assert config["tagFormat"] == "v${version}"
    assert config.get("initialVersion"), "initialVersion is required for a fresh clone"
    assert "github" in config["plugins"]
    assert any(branch.get("name") == "main" for branch in config["branches"])


def test_release_workflow_uses_big_release_without_node() -> None:
    """CI validates and previews with big-release; Node is not a dependency."""
    workflow = _load_yaml(REPO_ROOT / ".github/workflows/test-build-release.yml")
    steps = workflow["jobs"]["release"]["steps"]
    runs = "\n".join(step.get("run", "") for step in steps)
    uses = "\n".join(step.get("uses", "") for step in steps)

    assert "big-release validate" in runs
    assert "big-release release --dry-run" in runs
    assert "big-release release --verbose" in runs
    assert "actions/setup-node" not in uses


def test_justfile_release_path_uses_big_release() -> None:
    """The manual gh-release path is gone; local recipes use big-release."""
    text = (REPO_ROOT / "justfile").read_text()

    assert "release-validate:" in text
    assert "release-dry-run:" in text
    assert "big-release validate" in text
    assert "big-release release --dry-run" in text
    assert "gh release create" not in text
