"""Behaviour of the bundled CI/CD Pipeline Audit check script.

The script lives in ``data/checks/ci-cd-pipeline-audit.yaml``. Each test builds a
fixture ``.github/workflows`` directory and runs the real script as a subprocess,
the same way the checks engine does, then reads the result table it prints.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

CHECK_FILE = Path(__file__).parents[2] / "data" / "checks" / "ci-cd-pipeline-audit.yaml"

SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"


@pytest.fixture(scope="session")
def audit_script(tmp_path_factory: pytest.TempPathFactory) -> Path:
    script = yaml.safe_load(CHECK_FILE.read_text())["script"]
    path = tmp_path_factory.mktemp("audit-script") / "audit.py"
    path.write_text(script)
    return path


class Audit:
    def __init__(self, script: Path, repo: Path) -> None:
        self.script = script
        self.repo = repo
        self.env: dict[str, str] = {}

    def workflow(self, name: str, body: str) -> None:
        wf_dir = self.repo / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        (wf_dir / name).write_text(textwrap.dedent(body))

    def run(self, *args: str) -> AuditResult:
        env = {
            k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")
        }
        env.update({"REPO_FULL_NAME": "acme/widget", "BRANCH": "main", **self.env})
        proc = subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return AuditResult(proc.returncode, proc.stdout, proc.stderr)


class AuditResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.rows: list[tuple[str, str, str, str]] = []
        for line in stdout.splitlines():
            if not line.startswith("| ") or line.startswith("| Check ID"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|", 3)]
            if len(cells) == 4 and cells[1] in ("PASS", "FAIL"):
                self.rows.append((cells[0], cells[1], cells[2], cells[3]))

    def find(self, prefix: str) -> list[tuple[str, str, str, str]]:
        return [r for r in self.rows if r[0].startswith(prefix)]

    def status(self, prefix: str) -> list[str]:
        return [r[1] for r in self.find(prefix)]


@pytest.fixture
def audit(audit_script: Path, tmp_path: Path) -> Audit:
    return Audit(audit_script, tmp_path)


PIPELINE = """\
name: Test Build Release
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
"""


def scoped(name: str = "scoped.yml") -> tuple[str, str]:
    return name, PIPELINE.replace("jobs:", "permissions:\n  contents: read\njobs:")


# ── #50 / #51: rule 9a ───────────────────────────────────────────────────────


def test_9a_reports_every_workflow_not_just_the_first_scoped(audit: Audit) -> None:
    audit.workflow("a-open.yml", PIPELINE)
    audit.workflow(*scoped("b-scoped.yml"))
    audit.workflow("c-open.yml", PIPELINE)
    result = audit.run()
    rows = {r[0]: r[1] for r in result.find("9a.")}
    assert rows == {
        "9a. Permissions block [a-open.yml]": "FAIL",
        "9a. Permissions block [b-scoped.yml]": "PASS",
        "9a. Permissions block [c-open.yml]": "FAIL",
    }


def test_9a_job_level_permissions_on_every_job_pass(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        PIPELINE.replace(
            "    runs-on: ubuntu-22.04\n",
            "    runs-on: ubuntu-22.04\n    permissions:\n      contents: read\n",
        ),
    )
    (row,) = audit.run().find("9a.")
    assert row[1] == "PASS"
    assert "job-level" in row[3]


def test_9a_top_level_permissions_still_pass(audit: Audit) -> None:
    audit.workflow(*scoped("test-build-release.yml"))
    (row,) = audit.run().find("9a.")
    assert row[1] == "PASS"
    assert "contents" in row[3]


def test_9a_names_the_job_that_inherits_the_default(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        PIPELINE
        + """\
  lint:
    runs-on: ubuntu-22.04
    permissions:
      contents: read
    steps:
      - run: echo
""",
    )
    (row,) = audit.run().find("9a.")
    assert row[1] == "FAIL"
    assert "test" in row[3]
    assert "lint" not in row[3]
