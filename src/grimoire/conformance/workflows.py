"""Rules that inspect ``.github/workflows/*.yml``.

The canonical layout is the copy-once pair from danielvm-git/.github
``workflow-templates/``: ``test-build-release.yml`` plus ``deploy.yml``, where the
deploy workflow runs on ``workflow_run`` of the pipeline, gated on success on the
default branch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from grimoire.conformance import RuleContext, RuleResult

TBR_NAMES = ("test-build-release.yml", "test-build-release.yaml")
DEPLOY_NAMES = ("deploy.yml", "deploy.yaml")
# Artifacts a test-build-release workflow hands to deploy.yml (BigBase / GitHub Pages).
DEPLOY_ARTIFACT_MARKERS = ("deploy-meta", "pages-site")
SHA_RE = re.compile(r"[0-9a-f]{40}")
BIGBASE_ACTION = "danielvm-git/.github/actions/bigbase-deploy@"


@dataclass
class Workflow:
    path: Path
    data: dict[str, Any]
    text: str
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def file(self) -> str:
        return self.path.name

    @property
    def name(self) -> str:
        # GitHub falls back to the file path when a workflow has no name.
        return str(self.data.get("name") or f".github/workflows/{self.file}")

    @property
    def triggers(self) -> dict[str, Any]:
        on = self.data.get("on")
        if isinstance(on, str):
            return {on: None}
        if isinstance(on, list):
            return {str(t): None for t in on}
        if isinstance(on, dict):
            return on
        return {}


def load_workflows(root: Path) -> tuple[list[Workflow], list[str]]:
    """Parse every workflow file. Returns (workflows, problems)."""
    wf_dir = root / ".github" / "workflows"
    workflows: list[Workflow] = []
    problems: list[str] = []
    if not wf_dir.is_dir():
        return workflows, problems
    for path in sorted([*wf_dir.glob("*.yml"), *wf_dir.glob("*.yaml")]):
        text = path.read_text(errors="replace")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            problems.append(
                f"{path.name}: cannot parse YAML ({exc.__class__.__name__})"
            )
            continue
        if not isinstance(data, dict):
            problems.append(f"{path.name}: not a workflow mapping")
            continue
        # YAML 1.1 reads the bare key `on` as boolean True.
        if True in data and "on" not in data:
            data["on"] = data.pop(True)
        jobs = data.get("jobs")
        if not isinstance(jobs, dict) or not jobs:
            problems.append(f"{path.name}: has no jobs")
            jobs = {}
        jobs = {str(k): v for k, v in jobs.items() if isinstance(v, dict)}
        workflows.append(Workflow(path=path, data=data, text=text, jobs=jobs))
    return workflows, problems


def _first(workflows: list[Workflow], names: tuple[str, ...]) -> Workflow | None:
    return next((w for w in workflows if w.file in names), None)


def _only_reusable(wf: Workflow) -> bool:
    return set(wf.triggers) == {"workflow_call"}


def _norm(expr: Any) -> str:
    return re.sub(r"\s+", " ", str(expr or "")).replace('"', "'")


def ci_layout(ctx: RuleContext) -> RuleResult:
    """P0: the test-build-release.yml + deploy.yml pair, with deploy gated on success."""
    workflows, problems = load_workflows(ctx.repo_path)
    notes: list[str] = []
    tbr = _first(workflows, TBR_NAMES)
    if tbr is None:
        problems.append("missing .github/workflows/test-build-release.yml")
    for wf in workflows:
        if wf.file.startswith("ci-cd"):
            problems.append(
                f"{wf.file}: not the pattern; use test-build-release.yml + deploy.yml"
            )
    if tbr is None:
        return RuleResult.from_problems(problems, notes)

    for job_id, job in tbr.jobs.items():
        uses = str(job.get("uses", ""))
        step_uses = [
            str(s.get("uses", ""))
            for s in job.get("steps") or []
            if isinstance(s, dict)
        ]
        if "/deploy" in uses or any(u.startswith(BIGBASE_ACTION) for u in step_uses):
            problems.append(
                f"{tbr.file}: job '{job_id}' deploys; deploying belongs in deploy.yml"
            )

    needs_deploy = any(marker in tbr.text for marker in DEPLOY_ARTIFACT_MARKERS)
    deploy = _first(workflows, DEPLOY_NAMES)
    if deploy is None:
        if needs_deploy:
            problems.append(
                f"{tbr.file} uploads a deploy artifact but .github/workflows/deploy.yml is missing"
            )
        else:
            notes.append(
                "no deploy.yml: the pipeline hands no deploy artifact (CLI/library)"
            )
        return RuleResult.from_problems(problems, notes)

    run = deploy.triggers.get("workflow_run")
    if not isinstance(run, dict):
        problems.append(f"{deploy.file}: must trigger on workflow_run of '{tbr.name}'")
    else:
        watched = run.get("workflows") or []
        if isinstance(watched, str):
            watched = [watched]
        if tbr.name not in watched:
            problems.append(
                f"{deploy.file}: workflow_run watches {watched!r}, not '{tbr.name}'"
            )
        types = run.get("types") or []
        if "completed" not in (types if isinstance(types, list) else [types]):
            problems.append(f"{deploy.file}: workflow_run must use types: [completed]")
    gated = any(
        "workflow_run.conclusion == 'success'" in _norm(job.get("if"))
        and "workflow_run.head_branch ==" in _norm(job.get("if"))
        for job in deploy.jobs.values()
    )
    if not gated:
        problems.append(
            f"{deploy.file}: deploy job must be gated on "
            "workflow_run.conclusion == 'success' and the default head_branch"
        )
    return RuleResult.from_problems(problems, notes)


def ci_workflow_permissions(ctx: RuleContext) -> RuleResult:
    """P0: every workflow scopes its token, at workflow level or on every job."""
    workflows, problems = load_workflows(ctx.repo_path)
    for wf in workflows:
        top = wf.data.get("permissions")
        if top is not None:
            if top == "write-all":
                problems.append(
                    f"{wf.file}: permissions: write-all is not least privilege"
                )
            continue
        missing = [
            job_id for job_id, job in wf.jobs.items() if "permissions" not in job
        ]
        if missing:
            problems.append(
                f"{wf.file}: no workflow-level permissions and job(s) "
                f"{', '.join(missing)} inherit the default token scope"
            )
    return RuleResult.from_problems(problems)


def ci_job_timeouts(ctx: RuleContext) -> RuleResult:
    """P0: every job that runs steps sets timeout-minutes."""
    workflows, problems = load_workflows(ctx.repo_path)
    for wf in workflows:
        for job_id, job in wf.jobs.items():
            # Jobs that call a reusable workflow cannot set timeout-minutes.
            if "uses" in job:
                continue
            if "timeout-minutes" not in job:
                problems.append(f"{wf.file}: job '{job_id}' has no timeout-minutes")
    return RuleResult.from_problems(problems)


def ci_concurrency(ctx: RuleContext) -> RuleResult:
    """P0: workflow-level concurrency; the pipeline cancels, deploy never does."""
    workflows, problems = load_workflows(ctx.repo_path)
    for wf in workflows:
        if _only_reusable(wf):
            continue
        conc = wf.data.get("concurrency")
        if conc is None:
            problems.append(f"{wf.file}: no workflow-level concurrency group")
            continue
        cancel = (
            conc.get("cancel-in-progress", False) if isinstance(conc, dict) else False
        )
        if isinstance(cancel, str):
            problems.append(
                f"{wf.file}: cancel-in-progress is an expression; cannot verify"
            )
        elif wf.file in TBR_NAMES and cancel is not True:
            problems.append(f"{wf.file}: must set cancel-in-progress: true")
        elif wf.file in DEPLOY_NAMES and cancel is True:
            problems.append(f"{wf.file}: must not cancel an in-progress deploy")
    return RuleResult.from_problems(problems)


def _runner_labels(job: dict[str, Any]) -> list[str] | None:
    """Resolve runs-on to concrete labels; None when it cannot be resolved."""
    runs_on = job.get("runs-on")
    if isinstance(runs_on, dict):
        runs_on = runs_on.get("labels")
    raw = runs_on if isinstance(runs_on, list) else [runs_on]
    labels: list[str] = []
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    for item in raw:
        text = str(item)
        expr = re.fullmatch(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}", text)
        if expr:
            key = expr.group(1)
            values = matrix.get(key) if isinstance(matrix, dict) else None
            includes = matrix.get("include") if isinstance(matrix, dict) else None
            found = list(values) if isinstance(values, list) else []
            if isinstance(includes, list):
                found += [i[key] for i in includes if isinstance(i, dict) and key in i]
            if not found:
                return None
            labels += [str(v) for v in found]
        elif "${{" in text:
            return None
        else:
            labels.append(text)
    return labels


def ci_runner_pinned(ctx: RuleContext) -> RuleResult:
    """P0: no job runs on a floating *-latest runner image."""
    workflows, problems = load_workflows(ctx.repo_path)
    for wf in workflows:
        for job_id, job in wf.jobs.items():
            if "uses" in job:
                continue
            labels = _runner_labels(job)
            if labels is None:
                problems.append(
                    f"{wf.file}: job '{job_id}' runs-on is an expression; cannot verify"
                )
                continue
            latest = [label for label in labels if label.endswith("-latest")]
            if latest:
                problems.append(
                    f"{wf.file}: job '{job_id}' runs on {', '.join(latest)}; pin e.g. ubuntu-22.04"
                )
    return RuleResult.from_problems(problems)


def _all_uses(wf: Workflow) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for job_id, job in wf.jobs.items():
        if "uses" in job:
            refs.append((job_id, str(job["uses"])))
        for step in job.get("steps") or []:
            if isinstance(step, dict) and "uses" in step:
                refs.append((job_id, str(step["uses"])))
    return refs


def ci_actions_pinned(ctx: RuleContext) -> RuleResult:
    """P0: third-party actions pinned to a full SHA; nothing on @main/@master.

    First-party actions (``actions/*`` and the repo owner's own) may use tags.
    """
    workflows, problems = load_workflows(ctx.repo_path)
    first_party = {"actions"}
    if "/" in ctx.repo_full_name:
        first_party.add(ctx.repo_full_name.split("/", 1)[0].lower())
    for wf in workflows:
        for job_id, ref in _all_uses(wf):
            where = f"{wf.file}: job '{job_id}' uses {ref}"
            if ref.startswith("./"):
                continue
            if ref.startswith("docker://"):
                if "@sha256:" not in ref:
                    problems.append(f"{where}: pin the image by @sha256 digest")
                continue
            target, _, version = ref.partition("@")
            if not version:
                problems.append(f"{where}: not pinned")
                continue
            if version.lower() in ("main", "master"):
                problems.append(f"{where}: never use @main or @master")
                continue
            owner = target.split("/", 1)[0].lower()
            if owner not in first_party and not SHA_RE.fullmatch(version):
                problems.append(
                    f"{where}: third-party actions must be pinned to a 40-char SHA"
                )
    return RuleResult.from_problems(problems)


def bigbase_deploy(ctx: RuleContext) -> RuleResult:
    """P0 (BigBase projects): scoped token, the shared action, and a Health check step."""
    workflows, problems = load_workflows(ctx.repo_path)
    if not any("bigbase" in wf.text.lower() for wf in workflows):
        return RuleResult(passed=True, notes=["not a BigBase project"])
    for wf in workflows:
        for secret in ("BIGBASE_EMAIL", "BIGBASE_PASSWORD"):
            if secret in wf.text:
                problems.append(
                    f"{wf.file}: uses {secret}; deploy with BIGBASE_DEPLOY_TOKEN"
                )

    deploys = 0
    for wf in workflows:
        for job_id, job in wf.jobs.items():
            steps = [s for s in job.get("steps") or [] if isinstance(s, dict)]
            for idx, step in enumerate(steps):
                uses = str(step.get("uses", ""))
                if not uses.startswith(BIGBASE_ACTION):
                    continue
                deploys += 1
                where = f"{wf.file}: job '{job_id}'"
                version = uses.partition("@")[2]
                if version != "v1" and not SHA_RE.fullmatch(version):
                    problems.append(
                        f"{where}: pin bigbase-deploy to @v1 or a commit SHA"
                    )
                token = str((step.get("with") or {}).get("deploy_token", ""))
                if "secrets.BIGBASE_DEPLOY_TOKEN" not in token:
                    problems.append(
                        f"{where}: deploy_token must come from secrets.BIGBASE_DEPLOY_TOKEN"
                    )
                later = steps[idx + 1 :]
                if not any(
                    re.search(r"health\s*check", str(s.get("name", "")), re.I)
                    for s in later
                ):
                    problems.append(
                        f"{where}: needs a distinct 'Health check' step after the deploy"
                    )
    if deploys == 0:
        problems.append(f"no step uses {BIGBASE_ACTION}v1")
    return RuleResult.from_problems(problems)
