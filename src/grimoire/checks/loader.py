"""Load check definitions from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, Field, model_validator

from grimoire.targeting import TargetSpec

Priority = Literal["P0", "P1", "P2"]

# A pattern's priority fixes its severity: P0 gates landing (error), P1/P2 do not.
PRIORITY_SEVERITY: dict[str, str] = {"P0": "error", "P1": "warning", "P2": "warning"}


class CheckDefinition(BaseModel):
    """A single check definition loaded from YAML."""

    name: str
    slug: str = ""  # auto-derived from filename
    description: str
    targets: TargetSpec
    script: str
    schedule: str | None = None
    enabled: bool = True
    severity: Literal["warning", "error"] = "error"
    # Set on pattern-conformance checks; these feed the per-repo compliance score.
    priority: Priority | None = None
    # Commit-status context (e.g. ``grimoire/ci-audit``). When set, each result is
    # published to the branch head commit so branch protection can require it.
    publish_status: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def priority_matches_severity(self) -> Self:
        if (
            self.priority is not None
            and PRIORITY_SEVERITY[self.priority] != self.severity
        ):
            raise ValueError(
                f"priority {self.priority} requires severity "
                f"'{PRIORITY_SEVERITY[self.priority]}', got '{self.severity}'"
            )
        return self


def load_checks(data_dir: Path) -> list[CheckDefinition]:
    """Load all YAML check definitions from ``{data_dir}/checks/``.

    Derives slug from the filename (e.g. ``uv-lock-fresh.yaml`` → ``uv-lock-fresh``).
    Validates slug uniqueness and raises on any validation error.
    Returns an empty list if the directory doesn't exist or is empty.
    """
    checks_dir = data_dir / "checks"
    if not checks_dir.is_dir():
        return []

    seen_slugs: dict[str, Path] = {}
    checks: list[CheckDefinition] = []

    for yaml_file in sorted(checks_dir.glob("*.yaml")):
        slug = yaml_file.stem
        if slug in seen_slugs:
            raise ValueError(
                f"Duplicate check slug '{slug}': {seen_slugs[slug]} and {yaml_file}"
            )
        seen_slugs[slug] = yaml_file

        with open(yaml_file) as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(
                f"Expected a YAML mapping in {yaml_file}, got {type(raw).__name__}"
            )

        raw["slug"] = slug
        checks.append(CheckDefinition.model_validate(raw))

    return checks
