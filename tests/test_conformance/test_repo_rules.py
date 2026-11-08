"""File and git-history conformance rules."""

from __future__ import annotations

from pathlib import Path

from grimoire.conformance import repo as rr
from tests.test_conformance.conftest import RepoFactory


class TestAgentContextSymlinks:
    def test_passes_with_symlinks(self, repo: RepoFactory) -> None:
        assert rr.agent_context_symlinks(repo.ctx()).passed

    def test_regular_file_fails(self, repo: RepoFactory) -> None:
        repo.remove("CLAUDE.md")
        repo.write("CLAUDE.md", "# copy\n")
        result = rr.agent_context_symlinks(repo.ctx())
        assert not result.passed
        assert "CLAUDE.md is a regular file" in result.problems[0]

    def test_missing_fails(self, repo: RepoFactory) -> None:
        repo.remove("GEMINI.md")
        assert (
            "GEMINI.md is missing" in rr.agent_context_symlinks(repo.ctx()).problems[0]
        )

    def test_wrong_target_fails(self, repo: RepoFactory) -> None:
        repo.remove("CLAUDE.md")
        (repo.root / "CLAUDE.md").symlink_to("README.md")
        assert (
            "points to 'README.md'" in rr.agent_context_symlinks(repo.ctx()).problems[0]
        )

    def test_agents_md_missing_fails(self, tmp_path: Path) -> None:
        f = RepoFactory(tmp_path)
        (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
        (tmp_path / "GEMINI.md").symlink_to("AGENTS.md")
        result = rr.agent_context_symlinks(f.ctx())
        assert not result.passed
        assert "AGENTS.md must exist" in result.problems[0]


class TestReadme:
    def test_template_readme_passes(self, repo: RepoFactory) -> None:
        assert rr.readme_template(repo.ctx()).passed
        assert rr.preflight_documented(repo.ctx()).passed

    def test_missing_sections_and_badge_fail(self, repo: RepoFactory) -> None:
        repo.write("README.md", "# App\n\nSome text.\n")
        problems = rr.readme_template(repo.ctx()).problems
        assert len(problems) == 5
        assert "missing a GitHub Actions build status badge" in problems

    def test_no_readme_fails(self, repo: RepoFactory) -> None:
        repo.remove("README.md")
        assert not rr.readme_template(repo.ctx()).passed
        assert not rr.preflight_documented(repo.ctx()).passed

    def test_no_preflight_fails(self, repo: RepoFactory) -> None:
        repo.write(
            "README.md",
            "## Commands\n\n| Command | Purpose |\n| Test | `just test` |\n",
        )
        assert not rr.preflight_documented(repo.ctx()).passed

    def test_preflight_heading_passes(self, repo: RepoFactory) -> None:
        repo.write("README.md", "## Preflight\n\n```\njust check\n```\n")
        assert rr.preflight_documented(repo.ctx()).passed


class TestConventionsMd:
    def test_passes(self, repo: RepoFactory) -> None:
        assert rr.conventions_md(repo.ctx()).passed

    def test_missing_fails(self, repo: RepoFactory) -> None:
        repo.remove("CONVENTIONS.md")
        assert rr.conventions_md(repo.ctx()).problems == ["CONVENTIONS.md is missing"]

    def test_without_always_green_fails(self, repo: RepoFactory) -> None:
        repo.write("CONVENTIONS.md", "# Conventions\nUse tabs.\n")
        assert not rr.conventions_md(repo.ctx()).passed


class TestHistory:
    def test_conventional_history_passes(self, repo: RepoFactory) -> None:
        repo.git_commit("feat(web): add score")
        repo.git_commit("fix!: drop legacy flag")
        result = rr.conventional_commits(repo.ctx())
        assert result.passed
        assert result.notes == ["checked 2 commit(s)"]

    def test_non_conventional_subject_fails(self, repo: RepoFactory) -> None:
        repo.git_commit("feat: ok")
        repo.git_commit("Update stuff")
        result = rr.conventional_commits(repo.ctx())
        assert not result.passed
        assert result.problems[0].endswith("Update stuff")

    def test_coauthor_footer_fails(self, repo: RepoFactory) -> None:
        repo.git_commit("feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        assert not rr.no_ai_coauthors(repo.ctx()).passed

    def test_clean_history_passes(self, repo: RepoFactory) -> None:
        repo.git_commit("feat: x\n\nBody mentions co-authored-by: in prose only.")
        assert rr.no_ai_coauthors(repo.ctx()).passed

    def test_not_a_git_repo_raises(self, repo: RepoFactory) -> None:
        # The CLI turns this into a failure; the rule must not report a pass.
        try:
            rr.conventional_commits(repo.ctx())
        except RuntimeError as exc:
            assert "git log failed" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected RuntimeError")
