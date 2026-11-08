"""Fixture repos for conformance rules.

``GOOD_TBR`` / ``GOOD_DEPLOY`` mirror the danielvm-git/.github copy-once pair
(workflow-templates/test-build-release-python.yml + deploy-python.yml), trimmed
to the parts the rules read. Tests start from a compliant repo and break one thing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from grimoire.conformance import RuleContext

SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"

GOOD_TBR = f"""\
name: Test Build Release
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
concurrency:
  group: pipeline-${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true
env:
  SITE_URL: https://app.bigbase.click
jobs:
  test:
    runs-on: ubuntu-22.04
    timeout-minutes: 15
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@{SHA}  # v5
      - name: Preflight
        run: just preflight
  build:
    needs: test
    runs-on: ubuntu-22.04
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - name: Write deploy-meta
        run: echo '{{}}' > deploy-meta.json
      - uses: actions/upload-artifact@{SHA}  # v4
        with:
          name: deploy-meta
          path: deploy-meta.json
"""

GOOD_DEPLOY = """\
name: Deploy
on:
  workflow_run:
    workflows: ["Test Build Release"]
    types: [completed]
permissions:
  contents: read
  actions: read
concurrency:
  group: deploy-production
  cancel-in-progress: false
jobs:
  deploy:
    if: >
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_branch == 'main'
    runs-on: ubuntu-22.04
    timeout-minutes: 10
    steps:
      - name: Deploy to BigBase
        uses: danielvm-git/.github/actions/bigbase-deploy@v1
        with:
          site_id: ${{ secrets.BIGBASE_SITE_ID }}
          deploy_token: ${{ secrets.BIGBASE_DEPLOY_TOKEN }}
          skip_health_check: true
      - name: Health check
        run: curl -fsS "$SITE_URL"
"""

GOOD_README = """\
## Project title

## Build status

[![CI](https://github.com/danielvm-git/app/actions/workflows/test-build-release.yml/badge.svg)](https://github.com/danielvm-git/app/actions)

## Tech/framework used

## Commands

| Command | Purpose |
|---------|---------|
| Preflight | `just preflight` |

## Contribute

## 📄 License
"""


class RepoFactory:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def workflow(self, name: str, text: str) -> Path:
        return self.write(f".github/workflows/{name}", text)

    def remove(self, rel: str) -> None:
        (self.root / rel).unlink()

    def ctx(self, **kwargs: str) -> RuleContext:
        defaults = {"repo_full_name": "danielvm-git/app", "default_branch": "main"}
        defaults.update(kwargs)
        return RuleContext(repo_path=self.root, **defaults)  # type: ignore[arg-type]

    def git_commit(self, message: str) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        if not (self.root / ".git").exists():
            subprocess.run(
                ["git", "init", "-q", "-b", "main"], cwd=self.root, check=True, env=env
            )
        subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", message],
            cwd=self.root,
            check=True,
            env=env,
        )


@pytest.fixture
def repo(tmp_path: Path) -> RepoFactory:
    """A repo that satisfies every file/workflow rule."""
    f = RepoFactory(tmp_path)
    f.workflow("test-build-release.yml", GOOD_TBR)
    f.workflow("deploy.yml", GOOD_DEPLOY)
    f.write("README.md", GOOD_README)
    f.write("AGENTS.md", "# Agents\n")
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
    (tmp_path / "GEMINI.md").symlink_to("AGENTS.md")
    f.write("CONVENTIONS.md", "## Always Green\nFix it or log it.\n")
    return f
