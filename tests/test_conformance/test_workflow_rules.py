"""Workflow conformance rules: each passes on the template pair and fails when broken."""

from __future__ import annotations

from grimoire.conformance import workflows as wr
from tests.test_conformance.conftest import GOOD_DEPLOY, GOOD_TBR, SHA, RepoFactory


def _fails(result: object, fragment: str) -> None:
    assert not result.passed  # type: ignore[attr-defined]
    assert any(fragment in p for p in result.problems), result.problems  # type: ignore[attr-defined]


class TestTemplatePairPasses:
    def test_every_workflow_rule_passes_on_the_template_pair(
        self, repo: RepoFactory
    ) -> None:
        for rule in (
            wr.ci_layout,
            wr.ci_workflow_permissions,
            wr.ci_job_timeouts,
            wr.ci_concurrency,
            wr.ci_runner_pinned,
            wr.ci_actions_pinned,
            wr.bigbase_deploy,
        ):
            result = rule(repo.ctx())
            assert result.passed, (rule.__name__, result.problems)


class TestCiLayout:
    def test_missing_tbr_fails(self, repo: RepoFactory) -> None:
        repo.remove(".github/workflows/test-build-release.yml")
        _fails(
            wr.ci_layout(repo.ctx()), "missing .github/workflows/test-build-release.yml"
        )

    def test_ci_cd_file_is_not_the_pattern(self, repo: RepoFactory) -> None:
        repo.workflow("ci-cd.yml", GOOD_TBR.replace("Test Build Release", "CI/CD"))
        _fails(wr.ci_layout(repo.ctx()), "ci-cd.yml: not the pattern")

    def test_deploy_artifact_without_deploy_yml_fails(self, repo: RepoFactory) -> None:
        repo.remove(".github/workflows/deploy.yml")
        _fails(wr.ci_layout(repo.ctx()), "deploy.yml is missing")

    def test_cli_repo_without_deploy_passes(self, repo: RepoFactory) -> None:
        repo.remove(".github/workflows/deploy.yml")
        repo.workflow("test-build-release.yml", GOOD_TBR.replace("deploy-meta", "dist"))
        result = wr.ci_layout(repo.ctx())
        assert result.passed, result.problems
        assert any("CLI/library" in n for n in result.notes)

    def test_deploy_without_success_gate_fails(self, repo: RepoFactory) -> None:
        ungated = GOOD_DEPLOY.replace(
            "github.event.workflow_run.conclusion == 'success' &&\n", ""
        )
        repo.workflow("deploy.yml", ungated)
        _fails(wr.ci_layout(repo.ctx()), "must be gated")

    def test_deploy_watching_wrong_workflow_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml", GOOD_DEPLOY.replace('["Test Build Release"]', '["CI"]')
        )
        _fails(wr.ci_layout(repo.ctx()), "not 'Test Build Release'")

    def test_deploy_on_push_fails(self, repo: RepoFactory) -> None:
        on_push = GOOD_DEPLOY.replace(
            'workflow_run:\n    workflows: ["Test Build Release"]\n    types: [completed]',
            "push:\n    branches: [main]",
        )
        repo.workflow("deploy.yml", on_push)
        _fails(wr.ci_layout(repo.ctx()), "must trigger on workflow_run")

    def test_deploy_embedded_in_tbr_fails(self, repo: RepoFactory) -> None:
        embedded = GOOD_TBR + (
            "  deploy:\n    runs-on: ubuntu-22.04\n    timeout-minutes: 5\n"
            "    steps:\n      - uses: danielvm-git/.github/actions/bigbase-deploy@v1\n"
        )
        repo.workflow("test-build-release.yml", embedded)
        _fails(wr.ci_layout(repo.ctx()), "deploying belongs in deploy.yml")

    def test_unparseable_workflow_fails(self, repo: RepoFactory) -> None:
        repo.workflow("broken.yml", "jobs: [unclosed\n")
        _fails(wr.ci_layout(repo.ctx()), "cannot parse YAML")


class TestPermissions:
    def test_job_without_scope_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "lint.yml",
            "name: Lint\non: push\nconcurrency: lint\njobs:\n"
            "  a:\n    runs-on: ubuntu-22.04\n    timeout-minutes: 5\n"
            "    permissions:\n      contents: read\n    steps: [{run: 'true'}]\n"
            "  b:\n    runs-on: ubuntu-22.04\n    timeout-minutes: 5\n    steps: [{run: 'true'}]\n",
        )
        _fails(
            wr.ci_workflow_permissions(repo.ctx()),
            "lint.yml: no workflow-level permissions and job(s) b",
        )

    def test_write_all_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml",
            GOOD_DEPLOY.replace(
                "permissions:\n  contents: read\n  actions: read",
                "permissions: write-all",
            ),
        )
        _fails(wr.ci_workflow_permissions(repo.ctx()), "write-all")

    def test_every_workflow_is_checked_not_just_the_first(
        self, repo: RepoFactory
    ) -> None:
        # Regression for issue #50: a scoped workflow must not stop the scan.
        repo.workflow(
            "zz-late.yml",
            "name: Late\non: push\njobs:\n  x:\n    runs-on: ubuntu-22.04\n    steps: [{run: 'true'}]\n",
        )
        _fails(wr.ci_workflow_permissions(repo.ctx()), "zz-late.yml")


class TestTimeouts:
    def test_job_without_timeout_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace("    timeout-minutes: 15\n", "", 1),
        )
        _fails(wr.ci_job_timeouts(repo.ctx()), "job 'test' has no timeout-minutes")

    def test_reusable_caller_job_is_exempt(self, repo: RepoFactory) -> None:
        repo.workflow(
            "codeql.yml",
            "name: CodeQL\non: push\nconcurrency: codeql\npermissions: {}\njobs:\n"
            f"  scan:\n    uses: danielvm-git/.github/.github/workflows/codeql.yml@{SHA}\n",
        )
        assert wr.ci_job_timeouts(repo.ctx()).passed


class TestConcurrency:
    def test_missing_concurrency_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace(
                "concurrency:\n  group: pipeline-${{ github.workflow }}-${{ github.ref }}\n  cancel-in-progress: true\n",
                "",
            ),
        )
        _fails(wr.ci_concurrency(repo.ctx()), "no workflow-level concurrency")

    def test_tbr_must_cancel_in_progress(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace("cancel-in-progress: true", "cancel-in-progress: false"),
        )
        _fails(wr.ci_concurrency(repo.ctx()), "must set cancel-in-progress: true")

    def test_deploy_must_not_cancel(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml",
            GOOD_DEPLOY.replace(
                "cancel-in-progress: false", "cancel-in-progress: true"
            ),
        )
        _fails(wr.ci_concurrency(repo.ctx()), "must not cancel an in-progress deploy")

    def test_expression_cannot_be_verified(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace(
                "cancel-in-progress: true",
                "cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}",
            ),
        )
        _fails(wr.ci_concurrency(repo.ctx()), "cannot verify")


class TestRunnerPinned:
    def test_latest_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace("ubuntu-22.04", "ubuntu-latest", 1),
        )
        _fails(wr.ci_runner_pinned(repo.ctx()), "runs on ubuntu-latest")

    def test_matrix_latest_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "matrix.yml",
            "name: M\non: push\nconcurrency: m\npermissions: {}\njobs:\n  t:\n"
            "    strategy:\n      matrix:\n        os: [ubuntu-22.04, macos-latest]\n"
            "    runs-on: ${{ matrix.os }}\n    timeout-minutes: 5\n    steps: [{run: 'true'}]\n",
        )
        _fails(wr.ci_runner_pinned(repo.ctx()), "macos-latest")

    def test_unresolvable_expression_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace("ubuntu-22.04", "${{ vars.RUNNER }}", 1),
        )
        _fails(wr.ci_runner_pinned(repo.ctx()), "cannot verify")


class TestActionsPinned:
    def test_third_party_tag_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace(f"astral-sh/setup-uv@{SHA}", "astral-sh/setup-uv@v5"),
        )
        _fails(wr.ci_actions_pinned(repo.ctx()), "astral-sh/setup-uv@v5: third-party")

    def test_first_party_main_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml",
            GOOD_DEPLOY.replace("bigbase-deploy@v1", "bigbase-deploy@main"),
        )
        _fails(wr.ci_actions_pinned(repo.ctx()), "never use @main")

    def test_job_level_reusable_workflow_is_scanned(self, repo: RepoFactory) -> None:
        repo.workflow(
            "reuse.yml",
            "name: R\non: push\nconcurrency: r\npermissions: {}\njobs:\n"
            "  x:\n    uses: evil/repo/.github/workflows/x.yml@main\n",
        )
        _fails(
            wr.ci_actions_pinned(repo.ctx()), "evil/repo/.github/workflows/x.yml@main"
        )

    def test_docker_without_digest_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace(f"astral-sh/setup-uv@{SHA}", "docker://alpine:3.20"),
        )
        _fails(wr.ci_actions_pinned(repo.ctx()), "@sha256")

    def test_local_action_and_docker_digest_pass(self, repo: RepoFactory) -> None:
        digest = "docker://alpine@sha256:" + "a" * 64
        repo.workflow(
            "test-build-release.yml",
            GOOD_TBR.replace(
                f"astral-sh/setup-uv@{SHA}", "./.github/actions/setup"
            ).replace(
                "      - name: Preflight",
                f"      - uses: {digest}\n      - name: Preflight",
            ),
        )
        assert wr.ci_actions_pinned(repo.ctx()).passed

    def test_other_owner_is_third_party(self, repo: RepoFactory) -> None:
        # danielvm-git actions are first-party only for danielvm-git repos.
        _fails(
            wr.ci_actions_pinned(repo.ctx(repo_full_name="someone/else")),
            "bigbase-deploy@v1: third-party",
        )


class TestBigbaseDeploy:
    def test_non_bigbase_repo_passes(self, repo: RepoFactory) -> None:
        repo.remove(".github/workflows/deploy.yml")
        repo.workflow("test-build-release.yml", GOOD_TBR.replace("bigbase", "example"))
        result = wr.bigbase_deploy(repo.ctx())
        assert result.passed and result.notes == ["not a BigBase project"]

    def test_email_password_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml",
            GOOD_DEPLOY.replace(
                "deploy_token: ${{ secrets.BIGBASE_DEPLOY_TOKEN }}",
                "email: ${{ secrets.BIGBASE_EMAIL }}\n          password: ${{ secrets.BIGBASE_PASSWORD }}",
            ),
        )
        result = wr.bigbase_deploy(repo.ctx())
        _fails(result, "uses BIGBASE_EMAIL")
        _fails(result, "deploy_token must come from secrets.BIGBASE_DEPLOY_TOKEN")

    def test_missing_health_check_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml",
            GOOD_DEPLOY.replace(
                '      - name: Health check\n        run: curl -fsS "$SITE_URL"\n', ""
            ),
        )
        _fails(wr.bigbase_deploy(repo.ctx()), "Health check")

    def test_unpinned_action_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml",
            GOOD_DEPLOY.replace("bigbase-deploy@v1", "bigbase-deploy@main"),
        )
        _fails(wr.bigbase_deploy(repo.ctx()), "pin bigbase-deploy")

    def test_bigbase_without_shared_action_fails(self, repo: RepoFactory) -> None:
        repo.workflow(
            "deploy.yml",
            GOOD_DEPLOY.replace(
                "uses: danielvm-git/.github/actions/bigbase-deploy@v1",
                "run: curl -X POST https://bigbase.click/api/deploy",
            ).replace(
                "        with:\n          site_id: ${{ secrets.BIGBASE_SITE_ID }}\n          deploy_token: ${{ secrets.BIGBASE_DEPLOY_TOKEN }}\n          skip_health_check: true\n",
                "",
            ),
        )
        _fails(
            wr.bigbase_deploy(repo.ctx()),
            "no step uses danielvm-git/.github/actions/bigbase-deploy@v1",
        )
