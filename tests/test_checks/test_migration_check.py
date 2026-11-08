"""Behaviour of the bundled CI/CD Migration Status check script."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

CHECK_FILE = Path(__file__).parents[2] / "data" / "checks" / "ci-cd-migration.yaml"

TBR = """\
name: Test Build Release
on:
  push:
    branches: [main]
{env}jobs:
  test:
    runs-on: ubuntu-22.04
    steps:
      - run: echo
"""

GATE = (
    "github.event.workflow_run.conclusion == 'success' && "
    "github.event.workflow_run.head_branch == 'main'"
)

DEPLOY = """\
name: Deploy
on:
  workflow_run:
    workflows: ["Test Build Release"]
    types: [completed]
jobs:
{jobs}"""


def deploy_job(condition: str | None = GATE, needs: str = "") -> str:
    out = "  deploy:\n    runs-on: ubuntu-22.04\n"
    if needs:
        out += f"    needs: [{needs}]\n"
    if condition:
        out += f"    if: {condition}\n"
    return out + "    steps:\n      - run: echo\n"


def build_job(condition: str | None = GATE) -> str:
    return deploy_job(condition).replace("  deploy:", "  build:", 1)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(scope="session")
def script(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("migration") / "check.sh"
    path.write_text(yaml.safe_load(CHECK_FILE.read_text())["script"])
    return path


def write(repo: Path, name: str, body: str) -> None:
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / name).write_text(textwrap.dedent(body))


def run(script: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GRIMOIRE_PYTHON": sys.executable}
    return subprocess.run(
        ["bash", str(script)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def tbr(env: str = "") -> str:
    return TBR.format(env=env)


def test_gated_deploy_passes(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr())
    write(repo, "deploy.yml", DEPLOY.format(jobs=deploy_job()))
    proc = run(script, repo)
    assert proc.returncode == 0, proc.stdout
    assert "PASS" in proc.stdout


def test_gate_resolved_through_needs_chain_passes(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr())
    write(
        repo,
        "deploy.yml",
        DEPLOY.format(jobs=build_job() + deploy_job(condition=None, needs="build")),
    )
    assert run(script, repo).returncode == 0


@pytest.mark.parametrize(
    "condition", [None, "always()", "github.event.workflow_run.conclusion == 'success'"]
)
def test_ungated_deploy_fails(script: Path, repo: Path, condition: str | None) -> None:
    write(repo, "test-build-release.yml", tbr())
    write(repo, "deploy.yml", DEPLOY.format(jobs=deploy_job(condition)))
    proc = run(script, repo)
    assert proc.returncode == 1
    assert "gate" in proc.stdout


def test_deploy_following_a_different_workflow_fails(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr())
    write(
        repo,
        "deploy.yml",
        DEPLOY.format(jobs=deploy_job()).replace("Test Build Release", "Other"),
    )
    proc = run(script, repo)
    assert proc.returncode == 1
    assert "Test Build Release" in proc.stdout


def test_deploy_without_completed_type_fails(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr())
    write(
        repo,
        "deploy.yml",
        DEPLOY.format(jobs=deploy_job()).replace("[completed]", "[requested]"),
    )
    assert run(script, repo).returncode == 1


def test_cancel_in_progress_on_deploy_fails(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr())
    body = DEPLOY.format(jobs=deploy_job()).replace(
        "jobs:", "concurrency:\n  group: d\n  cancel-in-progress: true\njobs:"
    )
    write(repo, "deploy.yml", body)
    proc = run(script, repo)
    assert proc.returncode == 1
    assert "cancel-in-progress" in proc.stdout


def test_cli_library_repo_without_deploy_passes(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr())
    proc = run(script, repo)
    assert proc.returncode == 0, proc.stdout
    assert "CLI — no hosted deploy" in proc.stdout


@pytest.mark.parametrize(
    "env", ["env:\n  SITE_URL: https://x.example\n", "env:\n  APP_TYPE: web\n"]
)
def test_hosted_app_without_deploy_still_fails(
    script: Path, repo: Path, env: str
) -> None:
    write(repo, "test-build-release.yml", tbr(env))
    proc = run(script, repo)
    assert proc.returncode == 1
    assert "Missing separate deploy" in proc.stdout


def test_explicit_opt_out_passes_even_with_hosting_marker(
    script: Path, repo: Path
) -> None:
    write(
        repo,
        "test-build-release.yml",
        tbr("env:\n  SITE_URL: https://x.example\n  BIGPOWERS_DEPLOY: none\n"),
    )
    assert run(script, repo).returncode == 0


def test_embedded_deploy_job_in_the_pipeline_fails(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr() + deploy_job(condition=None))
    proc = run(script, repo)
    assert proc.returncode == 1
    assert "Embedded deploy" in proc.stdout


def test_legacy_ci_cd_file_fails(script: Path, repo: Path) -> None:
    write(repo, "test-build-release.yml", tbr())
    write(repo, "deploy.yml", DEPLOY.format(jobs=deploy_job()))
    write(repo, "ci-cd-main.yml", tbr())
    proc = run(script, repo)
    assert proc.returncode == 1
    assert "ci-cd-main.yml" in proc.stdout


def test_old_single_file_layout_fails(script: Path, repo: Path) -> None:
    write(repo, "ci.yml", tbr())
    proc = run(script, repo)
    assert proc.returncode == 1
    assert "No recognizable workflow pattern" in proc.stdout


def test_missing_workflows_dir_fails(script: Path, repo: Path) -> None:
    assert run(script, repo).returncode == 1
