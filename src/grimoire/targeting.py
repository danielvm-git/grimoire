"""Shared target resolution for checks and actions."""

from __future__ import annotations

import asyncio
import os
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator
from typing_extensions import Self

if TYPE_CHECKING:
    from grimoire.models import TrackedRepository
    from grimoire.workspace.manager import WorkspaceManager

_TARGETING_TIMEOUT = 30

# Alias the builtin so the ``list`` *field* on TargetSpec doesn't shadow the
# type during deferred annotation evaluation (from __future__ import annotations).
_List = list


class TargetSpec(BaseModel):
    """Targeting configuration. Exactly one field must be set."""

    list: _List[str] | None = None
    regex: str | None = None
    script: str | None = None

    @model_validator(mode="after")
    def exactly_one_target(self) -> Self:
        set_count = sum(1 for v in [self.list, self.regex, self.script] if v is not None)
        if set_count != 1:
            raise ValueError("Exactly one of 'list', 'regex', or 'script' must be set")
        return self


async def resolve_targets(
    targets: TargetSpec,
    repos: _List[TrackedRepository],
    workspace: WorkspaceManager,
) -> _List[TrackedRepository]:
    """Resolve which repos a check/action applies to.

    - list: filter repos whose full_name is in targets.list
    - regex: filter repos whose full_name matches the regex pattern
    - script: run the script in each repo's default branch workdir;
              include repo if exit code is 0.
    """
    if targets.list is not None:
        allowed = set(targets.list)
        return [r for r in repos if r.full_name in allowed]

    if targets.regex is not None:
        pattern = re.compile(targets.regex)
        return [r for r in repos if pattern.search(r.full_name)]

    # script targeting
    assert targets.script is not None
    matched: _List[TrackedRepository] = []
    env = {**os.environ, **workspace.get_env()}
    for repo in repos:
        cwd = workspace.get_workdir(repo.full_name, repo.default_branch)
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_shell(
                targets.script,
                cwd=cwd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            rc = await asyncio.wait_for(proc.wait(), timeout=_TARGETING_TIMEOUT)
            if rc == 0:
                matched.append(repo)
        except (asyncio.TimeoutError, OSError):
            # timeout or exec failure → exclude
            if proc is not None and proc.returncode is None:
                proc.kill()
    return matched
