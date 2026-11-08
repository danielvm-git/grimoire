"""Behaviour of the bundled CI/CD Pipeline Audit check script.

The script lives in ``data/checks/ci-cd-pipeline-audit.yaml``. Each test builds a
fixture ``.github/workflows`` directory and runs the real script as a subprocess,
the same way the checks engine does, then reads the result table it prints.
"""

from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import textwrap
import threading
from collections.abc import Callable, Iterator
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
            if len(cells) == 4 and cells[1] in ("PASS", "FAIL", "UNKNOWN"):
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
    failed_ids = {r[0].split(".")[0] for r in result.rows if r[1] != "PASS"}
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
    fails = len([r for r in result.rows if r[1] != "PASS"])
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


# ── #58 / #60.4: rule 8b dependency caching ──────────────────────────────────


def _cache_wf(step: str) -> str:
    return PIPELINE + "      " + step.replace("\n", "\n      ") + "\n"


@pytest.mark.parametrize(
    ("step", "mechanism"),
    [
        ("- uses: actions/cache@v4\n  with:\n    path: ~/.cache", "actions/cache"),
        (
            "- uses: actions/setup-python@v5\n  with:\n    cache: pip",
            "setup-python cache=pip",
        ),
        (
            "- uses: actions/setup-python@v5\n  with:\n    cache: uv",
            "setup-python cache=uv",
        ),
        (
            "- uses: actions/setup-node@v4\n  with:\n    cache: 'npm'",
            "setup-node cache=npm",
        ),
        (
            "- uses: actions/setup-go@v5\n  with:\n    cache: true",
            "setup-go cache=true",
        ),
        (
            "- uses: astral-sh/setup-uv@v5\n  with:\n    enable-cache: true",
            "setup-uv enable-cache",
        ),
        ("- uses: Swatinem/rust-cache@v2", "rust-cache"),
    ],
)
def test_caching_recognised_mechanisms(audit: Audit, step: str, mechanism: str) -> None:
    audit.workflow("test-build-release.yml", _cache_wf(step))
    (row,) = audit.run().find("8b.")
    assert row[1] == "PASS"
    assert mechanism in row[3]
    assert row[2] == "test-build-release.yml"


def test_caching_setup_python_cache_true_is_not_caching(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        _cache_wf("- uses: actions/setup-python@v5\n  with:\n    cache: true"),
    )
    rows = audit.run().find("8b.")
    assert [r[1] for r in rows] == ["FAIL", "FAIL"]
    assert any("pip|poetry|pipenv|uv" in r[3] for r in rows)


def test_caching_keyword_in_a_script_does_not_count(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml", _cache_wf("- run: echo 'cache: true actions/cache'")
    )
    (row,) = audit.run().find("8b.")
    assert row[1] == "FAIL"


# ── #53: rule 5e deploy authentication ───────────────────────────────────────

DEPLOY = """\
name: Deploy
on:
  workflow_run:
    workflows: [Test Build Release]
    types: [completed]
{perms}jobs:
  deploy:
    runs-on: ubuntu-22.04
    environment: production
{job_perms}    steps:
      - name: Verify artifact
        run: test -f dist/index.html
      - name: Publish
        run: {publish}
"""


def _deploy(perms: str = "", job_perms: str = "", publish: str = "echo deploy") -> str:
    return DEPLOY.format(perms=perms, job_perms=job_perms, publish=publish)


def _auth_row(result: AuditResult) -> tuple[str, str, str, str]:
    (row,) = result.find("5e.")
    return row


def test_deploy_auth_oidc_job_permission_passes_and_is_named(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow(
        "deploy.yml",
        _deploy(
            job_perms="    permissions:\n      pages: write\n      id-token: write\n"
        ),
    )
    row = _auth_row(audit.run())
    assert row[1] == "PASS"
    assert "OIDC (id-token: write)" in row[3]


def test_deploy_auth_oidc_top_level_permission_passes(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow("deploy.yml", _deploy(perms="permissions:\n  id-token: write\n"))
    assert "OIDC" in _auth_row(audit.run())[3]


def test_deploy_auth_secret_passes_and_names_the_secret(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow(
        "deploy.yml", _deploy(publish="npm publish --token ${{ secrets.NPM_TOKEN }}")
    )
    row = _auth_row(audit.run())
    assert row[1] == "PASS"
    assert "secrets: NPM_TOKEN" in row[3]


def test_deploy_auth_neither_fails(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow("deploy.yml", _deploy())
    row = _auth_row(audit.run())
    assert row[1] == "FAIL"
    assert "id-token: write" in row[3]


def test_deploy_auth_id_token_read_is_not_oidc(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow("deploy.yml", _deploy(perms="permissions:\n  id-token: none\n"))
    assert _auth_row(audit.run())[1] == "FAIL"


# ── #60.1 / #60.2: sequencing and triggers ───────────────────────────────────


def _graph(**needs: list[str]) -> str:
    out = PIPELINE.split("jobs:")[0] + "jobs:\n"
    for job, deps in needs.items():
        name = job.replace("_", "-")
        out += f"  {name}:\n    runs-on: ubuntu-22.04\n"
        if deps:
            out += f"    needs: [{', '.join(d.replace('_', '-') for d in deps)}]\n"
        out += "    steps:\n      - run: echo\n"
    return out


def test_sequencing_build_reaches_test_through_intermediate_jobs(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        _graph(
            lint=[],
            test_sqlite=["lint"],
            test_ui=["lint"],
            verify=["test_sqlite"],
            release=["verify", "test_ui"],
            build=["release"],
        ),
    )
    result = audit.run()
    assert result.status("3c.") == ["PASS"]
    assert result.status("3d.") == ["PASS"]


def test_sequencing_classic_build_then_release_still_passes(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        _graph(lint=[], test=["lint"], build=["test"], release=["build"]),
    )
    result = audit.run()
    assert result.status("3c.") == ["PASS"]
    assert result.status("3d.") == ["PASS"]


def test_sequencing_build_with_no_path_to_test_is_critical(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        _graph(lint=[], test=["lint"], build=[], release=["build"]),
    )
    result = audit.run()
    assert result.status("3c.") == ["FAIL"]
    assert result.returncode == 2


def test_sequencing_unrelated_build_and_release_fail_3d(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        _graph(test=[], build=["test"], release=["test"]),
    )
    assert audit.run().status("3d.") == ["FAIL"]


AUX = """\
name: PR review
on:
  pull_request:
  issue_comment:
jobs:
  review:
    runs-on: ubuntu-22.04
    steps:
      - run: echo
"""


def test_push_trigger_not_required_on_auxiliary_workflows(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow("pr-review.yaml", AUX)
    rows = {r[0]: r[1] for r in audit.run().find("2a.")}
    assert rows["2a. push trigger [test-build-release.yml]"] == "PASS"
    assert all(v == "PASS" for v in rows.values())


def test_push_trigger_still_required_on_primary_pipeline(audit: Audit) -> None:
    audit.workflow(
        "test-build-release.yml",
        PIPELINE.replace("  push:\n    branches: [main]\n", ""),
    )
    assert audit.run().status("2a.") == ["FAIL"]


# ── #52: rules 7a/7b read branch protection from the API ─────────────────────


class FakeGitHub:
    """Tiny GitHub API stand-in keyed by request path."""

    def __init__(self, routes: dict[str, tuple[int, object]]) -> None:
        self.routes = routes
        self.paths: list[str] = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                outer.paths.append(self.path)
                status, body = outer.routes.get(
                    self.path, (404, {"message": "Not Found"})
                )
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args: object) -> None:
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


PROTECTION = "/repos/acme/widget/branches/main/protection"
RULES = "/repos/acme/widget/rules/branches/main"


@pytest.fixture
def github() -> Iterator[Callable[[dict[str, tuple[int, object]]], FakeGitHub]]:
    servers: list[FakeGitHub] = []

    def make(routes: dict[str, tuple[int, object]]) -> FakeGitHub:
        servers.append(FakeGitHub(routes))
        return servers[-1]

    yield make
    for server in servers:
        server.close()


def _with_api(audit: Audit, fake: FakeGitHub, token: str = "t") -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.env.update({"GITHUB_API_URL": fake.url, "DEFAULT_BRANCH": "main"})
    if token:
        audit.env["GH_TOKEN"] = token


def _env_run(audit: Audit) -> AuditResult:
    return audit.run()


def test_branch_protection_404_fails_both_rules(audit: Audit, github) -> None:
    _with_api(audit, github({}))
    result = _env_run(audit)
    assert result.status("7a.") == ["FAIL"]
    assert result.status("7b.") == ["FAIL"]
    assert "not protected" in result.find("7a.")[0][3]


def test_branch_protection_full_classic_protection_passes(audit: Audit, github) -> None:
    body = {
        "required_status_checks": {"contexts": ["test"], "checks": []},
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "enforce_admins": {"enabled": True},
    }
    _with_api(audit, github({PROTECTION: (200, body)}))
    result = _env_run(audit)
    assert result.status("7a.") == ["PASS"]
    assert result.status("7b.") == ["PASS"]
    assert "test" in result.find("7a.")[0][3]


def test_branch_protection_without_required_checks_fails_7a(
    audit: Audit, github
) -> None:
    body = {
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "enforce_admins": {"enabled": True},
    }
    _with_api(audit, github({PROTECTION: (200, body)}))
    result = _env_run(audit)
    assert result.status("7a.") == ["FAIL"]
    assert result.status("7b.") == ["PASS"]


def test_branch_protection_admins_may_push_directly_fails_7b(
    audit: Audit, github
) -> None:
    body = {
        "required_status_checks": {"contexts": ["test"]},
        "required_pull_request_reviews": {},
        "enforce_admins": {"enabled": False},
    }
    _with_api(audit, github({PROTECTION: (200, body)}))
    assert _env_run(audit).status("7b.") == ["FAIL"]


def test_branch_protection_rulesets_satisfy_both(audit: Audit, github) -> None:
    rules = [
        {"type": "pull_request", "parameters": {}},
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": "test"}]},
        },
    ]
    _with_api(audit, github({RULES: (200, rules)}))
    result = _env_run(audit)
    assert result.status("7a.") == ["PASS"]
    assert result.status("7b.") == ["PASS"]


def test_branch_protection_unreadable_is_unknown_never_pass(
    audit: Audit, github
) -> None:
    _with_api(audit, github({PROTECTION: (403, {}), RULES: (403, {})}))
    result = _env_run(audit)
    assert result.status("7a.") == ["UNKNOWN"]
    assert result.status("7b.") == ["UNKNOWN"]
    assert "403" in result.find("7a.")[0][3]


def test_branch_protection_without_token_is_unknown(audit: Audit, github) -> None:
    fake = github({})
    _with_api(audit, fake, token="")
    result = _env_run(audit)
    assert result.status("7a.") == ["UNKNOWN"]
    assert fake.paths == []


# ── #57: stable rule IDs and --json ──────────────────────────────────────────


def _json_run(audit: Audit) -> tuple[AuditResult, dict]:
    result = audit.run("--json")
    return result, json.loads(result.stdout)


def test_json_emits_one_object_per_rule(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow("other.yml", PIPELINE)
    table = audit.run()
    result, doc = _json_run(audit)
    assert result.returncode == table.returncode
    assert len(doc["rules"]) == len(table.rows)
    for rule in doc["rules"]:
        assert rule["status"] in ("pass", "fail", "unknown")
        assert rule["rule"].startswith("CI-")
        assert {"title", "file", "remediation"} <= rule.keys()
    assert doc["summary"]["failed"] == len([r for r in table.rows if r[1] != "PASS"])


def test_json_failed_rule_has_severity_and_remediation(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    _, doc = _json_run(audit)
    perms = [r for r in doc["rules"] if r["rule"] == "CI-PERM-001"]
    assert len(perms) == 1
    assert perms[0]["status"] == "fail"
    assert perms[0]["severity"] == "medium"
    assert perms[0]["file"] == "test-build-release.yml"
    assert "permissions" in perms[0]["remediation"]


def test_json_ids_are_stable_and_unmapped_free(audit: Audit) -> None:
    audit.workflow("test-build-release.yml", PIPELINE)
    audit.workflow(
        "deploy.yml",
        _deploy(job_perms="    permissions:\n      id-token: write\n"),
    )
    _, doc = _json_run(audit)
    ids = [r["rule"] for r in doc["rules"]]
    assert "CI-UNMAPPED" not in ids
    by_title = {r["title"]: r["rule"] for r in doc["rules"]}
    assert by_title["Branch protection — status checks"] == "CI-PROTECT-001"
    assert by_title["Branch protection — no direct push"] == "CI-PROTECT-002"
    assert by_title["Deploy authenticates (OIDC or secret)"] == "CI-DEPLOY-AUTH-001"


def test_json_with_no_workflows_is_still_valid_json(audit: Audit) -> None:
    result, doc = _json_run(audit)
    assert result.returncode == 0
    assert doc["summary"]["failed"] == 0
    assert doc["rules"][0]["rule"] == "CI-WORKFLOWS-001"
