# Module 9: Conformance Rules

Check every tracked repo against the portfolio patterns defined in the template repo `danielvm-git/.github`. Each pattern is one rule, implemented as tested Python, and exposed as one check definition in `data/checks/`.

**Dependencies:** Module 1 (config), Module 4 (checks engine: the `priority` field and the check scripts that call the rules).

## 9.1 — Source of truth and grades

Patterns come from the template repo. Its checklist `docs/how-to/align-existing-repo.md` grades each section:

| Grade | Meaning | Check severity | Effect |
|---|---|---|---|
| **P0** | Blocks a PR from landing | `error` | A failure turns the repo red and lowers the score |
| **P1** | Should be done | `warning` | A failure lowers the score but does not change repo health |
| **P2** | Nice to have | `warning` | Not scored |

Patterns with no grade in the template are **not** implemented. Grade them in the template first, then add a rule.

The canonical CI/CD layout is the copy-once pair `test-build-release.yml` + `deploy.yml`. Docs that call a thin `ci-cd.yml` the recommended layout are out of date.

## 9.2 — Rules

**Package:** `src/grimoire/conformance/`

| Slug | Grade | File | Fails when |
|---|---|---|---|
| `agent-context-symlinks` | P0 | `repo.py` | `AGENTS.md` is missing, or `CLAUDE.md`/`GEMINI.md` is not a symlink to it |
| `ci-layout` | P0 | `workflows.py` | No `test-build-release.yml`; any `ci-cd*.yml`; deploy steps in the pipeline; a pipeline that uploads `deploy-meta`/`pages-site` without `deploy.yml`; `deploy.yml` not on `workflow_run` (types `completed`) of the pipeline's `name`, or not gated on `workflow_run.conclusion == 'success'` and `workflow_run.head_branch ==` |
| `ci-workflow-permissions` | P0 | `workflows.py` | A workflow has no top-level `permissions` and a job has none; or `write-all` |
| `ci-job-timeouts` | P0 | `workflows.py` | A job with steps has no `timeout-minutes` (jobs that call a reusable workflow are exempt) |
| `ci-concurrency` | P0 | `workflows.py` | A non-reusable workflow has no top-level `concurrency`; the pipeline does not cancel in progress; `deploy.yml` does; or the value is an expression |
| `ci-runner-pinned` | P0 | `workflows.py` | Any `runs-on` label ends with `-latest` (matrix values are resolved), or `runs-on` is an unresolvable expression |
| `ci-actions-pinned` | P0 | `workflows.py` | A step or job `uses:` is on `@main`/`@master`; a third-party ref is not a 40-char SHA; a `docker://` ref has no `@sha256:` digest. First-party = `actions/*` and the repo owner. `./` actions are skipped |
| `branch-protection` | P0 | `github.py` | The default branch allows force-pushes or deletion, is unprotected, or neither API can be read |
| `bigbase-deploy` | P0, BigBase repos | `workflows.py` | `BIGBASE_EMAIL`/`BIGBASE_PASSWORD` used; no `danielvm-git/.github/actions/bigbase-deploy@v1` (or SHA) step; `deploy_token` not from `secrets.BIGBASE_DEPLOY_TOKEN`; no later step named "Health check" |
| `readme-template` | P1 | `repo.py` | README lacks an Actions badge or a Build status / Tech/framework used / Contribute / License heading (the sections every stack template shares) |
| `preflight-documented` | P1 | `repo.py` | README has no `Preflight` table row or heading |
| `conventions-md` | P1 | `repo.py` | `CONVENTIONS.md` is missing or does not mention Always Green |
| `conventional-commits` | P1 | `repo.py` | Any of the last 50 non-merge commits has a non-Conventional subject (regex from `scripts/check-conventional-commits.sh`) |
| `no-ai-coauthors` | P1 | `repo.py` | Any of the last 50 non-merge commits has a `Co-authored-by:` footer |
| `pr-required` | P1 | `github.py` | The default branch is unprotected or its protection cannot be read (direct push is allowed: solo-owner policy) |

Branch protection may come from classic protection (`GET /repos/{repo}/branches/{branch}/protection`) or rulesets (`GET /repos/{repo}/rules/branches/{branch}`). Either one satisfies a rule.

### Interface

```python
@dataclass
class RuleContext:
    repo_path: Path
    repo_full_name: str = ""
    default_branch: str = "main"
    token: str = ""
    api_url: str = "https://api.github.com"

@dataclass
class RuleResult:
    passed: bool
    problems: list[str]
    notes: list[str]

def get_rules() -> dict[str, Callable[[RuleContext], RuleResult]]: ...
```

### CLI

`python -m grimoire.conformance <rule> [--path DIR]` reads `REPO_FULL_NAME`, `DEFAULT_BRANCH`, `GH_TOKEN`/`GITHUB_TOKEN` and `GITHUB_API_URL` from the environment. It prints `PASS <rule>` or `FAIL <rule>: N problem(s)` with one line per problem, and exits `0` only on a pass. A rule that raises exits `1` with `rule crashed`.

## 9.3 — Check definitions

Each rule has `data/checks/<slug>.yaml` with `priority`, the matching `severity`, a default-branch-only target (`[ "$BRANCH" = "$DEFAULT_BRANCH" ]`; `bigbase-deploy` also requires `bigbase` in a workflow), and the script `python3 -m grimoire.conformance <slug>`.

`ci-cd-migration` is superseded by `ci-layout` and ships `enabled: false`.

## 9.4 — Compliance score

**File:** `src/grimoire/web/compliance.py`

`compute_compliance(checks_by_branch) -> Compliance | None` counts the entries whose `priority` is P0 or P1. Not-run entries are counted in `not_run` and never as passing. It returns `None` when the repo has no pattern checks.

- `percent` = passed / (P0 + P1 results), rounded down; `None` when nothing ran.
- `tier` = `fail` if any P0 fails, `partial` if any P1 fails, else `pass`.

## Acceptance Criteria

- [ ] Every rule passes on a fixture that mirrors the template's copy-once pair, and fails on at least one fixture that breaks it
- [ ] No rule passes when it cannot read its input (YAML parse error, git error, API error, missing token)
- [ ] Every rule in `get_rules()` has a bundled check with `priority` set
- [ ] A P0 check with `severity: warning`, or a P1/P2 check with `severity: error`, fails to load
- [ ] The repo page shows the P0/P1 breakdown, and the dashboard matrix sorts by compliance
