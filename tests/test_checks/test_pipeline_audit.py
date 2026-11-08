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


# ── #56: summary footer comes from the failing rules ─────────────────────────


def _footer(stdout: str) -> str:
    lines = stdout.splitlines()
    start = next(i for i, line in enumerate(lines) if line[:1] in "❌⚠ℹ✅")
    return "\n".join(lines[start:])


def test_footer_names_only_rules_that_failed(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    result = audit.run()
    failed_ids = {r[0].split(".")[0] for r in result.rows if r[1] == "FAIL"}
    passed_ids = {r[0].split(".")[0] for r in result.rows if r[1] == "PASS"}
    footer = _footer(result.stdout)
    assert "(rollback, smoke test, artifact reuse)" not in footer
    assert "[3a]" in footer
    for rid in passed_ids - failed_ids:
        assert f"[{rid}]" not in footer


def test_headline_counts_equal_fail_rows(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow("other.yml", PIPELINE)
    result = audit.run()
    fails = len([r for r in result.rows if r[1] == "FAIL"])
    out = result.stdout
    assert f"Failed:       {fails}" in out
    counts = {
        level: int(out.split(f"{level}:")[1].split()[0])
        for level in ("Critical", "High", "Medium")
    }
    assert sum(counts.values()) == fails


# ── #55 / #60.3: rule 8a action pinning ──────────────────────────────────────

DIGEST = "sha256:" + "0e0ab10b" * 8


def _with_uses(*refs: str) -> str:
    steps = "\n".join(f"      - uses: {r}" for r in refs)
    return PIPELINE.replace("      - uses: actions/checkout@v4", steps)


def _pin_row(result: AuditResult) -> tuple[str, str, str, str]:
    (row,) = result.find("8a.")
    return row


def test_pinning_floating_major_passes_by_default_but_is_named(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", _with_uses("actions/checkout@v6"))
    row = _pin_row(audit.run())
    assert row[1] == "PASS"
    assert "floating-major" in row[3]
    assert "v6" in row[3]


def test_pinning_strict_mode_fails_floating_and_passes_sha(audit: Audit) -> None:
    audit.env["GRIMOIRE_AUDIT_STRICT_SHA_PINNING"] = "1"
    audit.workflow("test-build-release.yml", _with_uses(f"actions/checkout@{SHA}"))
    assert _pin_row(audit.run())[1] == "PASS"
    audit.workflow("test-build-release.yml", _with_uses("actions/checkout@v6"))
    row = _pin_row(audit.run())
    assert row[1] == "FAIL"
    assert "actions/checkout@v6" in row[3]


def test_pinning_sha_is_reported_as_sha(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", _with_uses(f"actions/checkout@{SHA}"))
    row = _pin_row(audit.run())
    assert row[1] == "PASS"
    assert "sha" in row[3]
    assert "floating" not in row[3]


def test_pinning_oci_digest_counts_as_pinned(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        _with_uses(
            f"docker://pragent/pr-agent@{DIGEST}",
            f"docker://ghcr.io/acme/tool:1.2@{DIGEST}",
        ),
    )
    row = _pin_row(audit.run())
    assert row[1] == "PASS"
    assert "digest" in row[3]


def test_pinning_branch_and_untagged_refs_fail(audit: Audit) -> None:
    audit.env["GRIMOIRE_AUDIT_STRICT_SHA_PINNING"] = ""
    audit.workflow(
        "test-build-release.yml",
        _with_uses("acme/tool@main", "docker://alpine:3.19"),
    )
    row = _pin_row(audit.run())
    assert row[1] == "FAIL"
    assert "acme/tool@main" in row[3]
    assert "docker://alpine:3.19" in row[3]


def test_pinning_ignores_local_actions(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", _with_uses("./.github/actions/setup"))
    assert _pin_row(audit.run())[1] == "PASS"


def test_pinning_checks_reusable_workflow_refs(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        PIPELINE
        + """\
  call:
    uses: acme/shared/.github/workflows/ci.yml@main
""",
    )
    row = _pin_row(audit.run())
    assert row[1] == "FAIL"
    assert "ci.yml@main" in row[3]
