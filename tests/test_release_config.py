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


def test_release_workflow_keeps_lockfile_in_sync() -> None:
    """The release sync step must regenerate and stage uv.lock."""
    workflow = _load_yaml(REPO_ROOT / ".github/workflows/test-build-release.yml")
    steps = workflow["jobs"]["release"]["steps"]
    sync_step = next(
        step
        for step in steps
        if step.get("name") == "Sync pyproject version and CHANGELOG"
    )
    script = sync_step["run"]

    assert "uv lock" in script, "the release step must regenerate uv.lock"
    assert "uv.lock" in script, "the release step must stage uv.lock"


def test_test_job_guards_lockfile_freshness() -> None:
    """CI must reject a stale uv.lock before uv sync silently repairs it.

    A runtime assertion cannot catch this drift: `uv sync`/`uv run` rewrite uv.lock
    in the runner before tests execute, so the tree always looks consistent. The
    guard therefore has to run first, in the workflow. Provenance:
    specs/bugs/registry.yaml release-workflow-skips-uv-lock.
    """
    workflow = _load_yaml(REPO_ROOT / ".github/workflows/test-build-release.yml")
    steps = workflow["jobs"]["test"]["steps"]
    names = [step.get("name", "") for step in steps]

    lock_check_index = next(
        (
            index
            for index, step in enumerate(steps)
            if "uv lock --check" in step.get("run", "")
        ),
        None,
    )
    assert lock_check_index is not None, (
        "the test job needs a 'uv lock --check' step so a stale uv.lock fails the build"
    )

    sync_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("run", "").strip().startswith("uv sync")
    )
    assert lock_check_index < sync_index, (
        f"uv lock --check must run before uv sync (steps: {names})"
    )
