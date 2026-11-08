# Pattern conformance

Grimoire checks that each tracked repository follows the portfolio patterns defined in [`danielvm-git/.github`](https://github.com/danielvm-git/.github). Each pattern is one check. Its grade comes from the template's checklist, [Align an existing repo](https://github.com/danielvm-git/.github/blob/main/docs/how-to/align-existing-repo.md).

| Grade | Meaning | Severity | On the dashboard |
|---|---|---|---|
| **P0** | Blocks a PR from landing | `error` | A failure turns the repo red and lowers its compliance score |
| **P1** | Should be done | `warning` | A failure lowers the compliance score only |

Patterns without a grade in the template have no check. To add one, grade it in the template first.

All pattern checks run on the default branch only, every 6 hours. Each check
calls `"$GRIMOIRE_PYTHON" -m grimoire.conformance <rule>`, so the rule runs with
Grimoire's own interpreter even when the server was started without the
virtualenv on `PATH` (for example `run.sh`).

## P0 checks

| Check | What it requires | Template source |
|---|---|---|
| `agent-context-symlinks` | `AGENTS.md` is a real file; `CLAUDE.md` and `GEMINI.md` are symlinks to it | Align §1 |
| `ci-layout` | Pipeline in `test-build-release.yml`. If it uploads a `deploy-meta` or `pages-site` artifact, a `deploy.yml` that runs on `workflow_run` of the pipeline (types `completed`) and only when `conclusion == 'success'` on the default branch. No `ci-cd*.yml`, and no deploy steps inside the pipeline | Align §3, `workflow-templates/` |
| `ci-workflow-permissions` | `permissions:` at workflow level, or on every job. Never `write-all` | Align §3 |
| `ci-job-timeouts` | `timeout-minutes` on every job that runs steps | Align §3 |
| `ci-concurrency` | A workflow-level `concurrency` group. `cancel-in-progress: true` on the pipeline, never on the deploy | Align §3 |
| `ci-runner-pinned` | No `*-latest` runner (use e.g. `ubuntu-22.04`) | Align §3 |
| `ci-actions-pinned` | Third-party actions pinned to a 40-character SHA. Nothing on `@main` or `@master`. `actions/*` and your own actions may use tags | Align §3 |
| `branch-protection` | The default branch blocks force-pushes and deletion (classic protection or rulesets) | Branch protection rules |
| `bigbase-deploy` | BigBase projects only: deploy with `danielvm-git/.github/actions/bigbase-deploy@v1` and `secrets.BIGBASE_DEPLOY_TOKEN`, never email/password, followed by a step named `Health check` | Align §4 |

## P1 checks

| Check | What it requires | Template source |
|---|---|---|
| `readme-template` | A GitHub Actions badge, and Build status, Tech/framework used, Contribute and License sections | Align §2, `templates/readmes/` |
| `preflight-documented` | A `Preflight` row in the README Commands table, or a Preflight section | Align §6 |
| `conventions-md` | `CONVENTIONS.md` exists and documents the Always Green rule | Align §5 |
| `conventional-commits` | The last 50 non-merge commits use Conventional Commits | `CONVENTIONS.md` |
| `no-ai-coauthors` | No `Co-authored-by:` footer in the last 50 non-merge commits | `CONVENTIONS.md` § Git Attribution |
| `pr-required` | The default branch requires a pull request with at least one approval | Branch protection rules |

## Compliance score

Each repository with pattern checks gets a score: the share of its P0 and P1 checks that pass.

- The **matrix** view has a sortable **Compliance** column. The **list** view shows the badge next to the repo name.
- The **repository** page shows `P0 passed/total` and `P1 passed/total` under the Checks header.
- The badge is red if any P0 fails, yellow if only P1 checks fail, and green otherwise. Hover it for the breakdown.
- Checks that have not run yet are listed as "not run" and never count as passing.

## A check never passes on what it cannot see

If a pattern check cannot read its input, it fails and says why. This covers an unparseable workflow, a git error, a missing token, or a branch protection API the token cannot read.

The branch protection checks need a token that can read repository administration settings. On a private repository on a free plan, GitHub does not expose branch protection, so those checks fail with "cannot verify".

## Run one rule by hand

```bash
cd path/to/repo
REPO_FULL_NAME=danielvm-git/my-repo GH_TOKEN=$(gh auth token) \
  uv run --project path/to/grimoire python -m grimoire.conformance ci-layout
```
