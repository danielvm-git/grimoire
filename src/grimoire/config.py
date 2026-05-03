"""YAML configuration schema and loader for Grimoire."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

_ENV_VAR_PATTERN = re.compile(r"^\$\{([^}]+)\}$")


def resolve_env_vars(raw: object) -> object:
    """Recursively walk a parsed YAML structure and resolve ``${ENV_VAR}`` references.

    Only exact-match string values are resolved (no partial interpolation).
    Raises ``ValueError`` for references to unset environment variables.
    """
    if isinstance(raw, str):
        match = _ENV_VAR_PATTERN.match(raw)
        if match:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(
                    f"Environment variable '{var_name}' is referenced in config but not set"
                )
            return value
        return raw
    if isinstance(raw, dict):
        return {k: resolve_env_vars(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [resolve_env_vars(item) for item in raw]
    return raw


# ---------------------------------------------------------------------------
# Config schema
# ---------------------------------------------------------------------------


class GitHubConfig(BaseModel):
    """GitHub API authentication."""

    token: str


class GitUserConfig(BaseModel):
    """Git user identity for commits."""

    name: str
    email: str


class SigningConfig(BaseModel):
    """Commit signing configuration."""

    key_path: Path
    format: Literal["ssh", "gpg"]


class GitConfig(BaseModel):
    """Git identity and signing — optional, only needed for actions that commit/push."""

    user: GitUserConfig
    signing: SigningConfig | None = None
    ssh_known_hosts: Path | None = None


class WorkflowFilter(BaseModel):
    """Include/exclude filter for GitHub Actions workflows (glob patterns on name)."""

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class StaticRepoSource(BaseModel):
    """A single repository specified by full name, with optional branch list."""

    repo: str
    branches: list[str] = Field(default_factory=list)
    workflows: WorkflowFilter = Field(default_factory=WorkflowFilter)


class TeamRepoSource(BaseModel):
    """All repositories belonging to a GitHub team, with optional exclusions."""

    team: str
    exclude: list[str] = Field(default_factory=list)
    workflows: WorkflowFilter = Field(default_factory=WorkflowFilter)


RepoSource = Annotated[Union[StaticRepoSource, TeamRepoSource], Field(discriminator=None)]


class StalenessConfig(BaseModel):
    """Thresholds for marking issues/PRs as stale."""

    pull_requests_days: int = 30
    issues_days: int = 365
    branches_days: int = 90

    # Percentage thresholds: highlight stale counts as problematic
    # when stale/open >= this percentage.
    problematic_stale_issues_pct: int = 20
    problematic_stale_prs_pct: int = 20


class HistoryConfig(BaseModel):
    """Configuration for historical snapshot retention."""

    retention_days: int = 90


class BacklogCategoryWeights(BaseModel):
    """Base importance weights for each backlog item category."""

    failing_workflow: float = 100.0
    failing_check_error: float = 80.0
    failing_check_warning: float = 30.0
    stale_pr: float = 50.0
    stale_issue: float = 20.0
    stale_branches: float = 10.0


class RepositoryWeightRule(BaseModel):
    """A rule mapping repositories to a backlog weight multiplier.

    Exactly one of ``regex`` or ``repos`` must be set.
    - ``regex``: fnmatch glob pattern matched against the full_name.
    - ``repos``: explicit list of full_name strings.
    """

    regex: str | None = None
    repos: list[str] | None = None
    weight: float = 1.0

    @model_validator(mode="after")
    def exactly_one_selector(self) -> Self:
        if (self.regex is None) == (self.repos is None):
            raise ValueError("Exactly one of 'regex' or 'repos' must be set")
        return self


class BacklogConfig(BaseModel):
    """Configuration for the Backlog (prioritised problem list) page."""

    category_weights: BacklogCategoryWeights = Field(default_factory=BacklogCategoryWeights)
    workflow_weights: dict[str, float] = Field(default_factory=dict)
    repository_weights: list[RepositoryWeightRule] = Field(default_factory=list)


class GrimoireConfig(BaseModel):
    """Top-level application configuration."""

    github: GitHubConfig
    git: GitConfig | None = None

    repositories: list[RepoSource]

    staleness: StalenessConfig = Field(default_factory=StalenessConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)
    backlog: BacklogConfig = Field(default_factory=BacklogConfig)
    refresh_schedule: str = "*/5 * * * *"

    data_dir: Path = Path("./data")
    workspace_dir: Path = Path("./workspace")
    database_path: Path = Path("./grimoire.db")
    log_file: Path = Path("./grimoire.log")

    @model_validator(mode="after")
    def at_least_one_repo_source(self) -> Self:
        if not self.repositories:
            raise ValueError("At least one repository source must be configured")
        return self


def _parse_repo_source(raw: dict) -> RepoSource:  # type: ignore[type-arg]
    """Disambiguate a repository source dict into the correct model."""
    if "repo" in raw:
        return StaticRepoSource.model_validate(raw)
    if "team" in raw:
        return TeamRepoSource.model_validate(raw)
    raise ValueError(f"Repository source must have either 'repo' or 'team' key, got: {raw}")


def load_config(path: Path | None = None) -> GrimoireConfig:
    """Load and validate the Grimoire configuration file.

    Resolution order for the config path:
    1. Explicit ``path`` argument.
    2. ``GRIMOIRE_CONFIG`` environment variable.
    3. ``./config.yaml`` in the current working directory.
    """
    if path is None:
        env_path = os.environ.get("GRIMOIRE_CONFIG")
        path = Path(env_path) if env_path else Path("config.yaml")

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping at the top level, got {type(raw).__name__}")

    resolved = resolve_env_vars(raw)
    assert isinstance(resolved, dict)

    # Manually parse the heterogeneous repositories list
    raw_repos = resolved.get("repositories", [])
    parsed_repos = [_parse_repo_source(r) for r in raw_repos]
    resolved["repositories"] = parsed_repos

    return GrimoireConfig.model_validate(resolved)
