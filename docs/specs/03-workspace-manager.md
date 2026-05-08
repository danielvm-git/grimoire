# Module 3: Repository Workspace Manager

Clone tracked repositories locally, manage branch checkouts, configure Git identity, and provide working directories for checks and actions to run in.

**Dependencies:** Module 1 (config), Module 2 (resolved repositories).

## 3.1 — Workspace Manager

**File:** `src/grimoire/workspace/manager.py`

### Responsibilities

- Clone repos into `{workspace_dir}/{owner}/{repo}/` if not already present.
- Pull latest changes for each observed branch.
- Provide a method to get a working directory for a given repo + branch.
- Configure Git identity (user.name, user.email) in each cloned repo.
- Set up signing (GPG or SSH) if configured.
- Add SSH keys to ssh-agent if configured.
- Export `GH_TOKEN` and `GITHUB_TOKEN` into the environment used by subprocesses.

### Interface

```python
class WorkspaceManager:
    def __init__(self, config: GrimoireConfig): ...

    async def setup(self, repos: list[TrackedRepository]) -> None:
        """Clone/update all repos. Configure git identity in each (if git config present)."""

    async def sync_all(self, repos: list[TrackedRepository]) -> None:
        """Fetch latest from remote for all repos with bounded concurrency."""

    async def sync_repo(self, repo: TrackedRepository) -> None:
        """Pull latest for all branches of a single repo."""

    async def reset_workdir(self, full_name: str, branch: str) -> Path:
        """
        Ensure the workdir for repo+branch is clean and up-to-date:
        git checkout {branch}, git reset --hard origin/{branch}, git clean -fdx.
        Must be called before each check/action execution.
        Returns the workdir path.
        """

    def get_workdir(self, full_name: str, branch: str) -> Path:
        """
        Return the path to the working directory for a repo+branch.
        Creates the worktree if it doesn't exist.
        """

    def get_env(self) -> dict[str, str]:
        """
        Return env vars to pass to subprocesses.
        Always includes GH_TOKEN, GITHUB_TOKEN.
        Includes GIT_AUTHOR_*/GIT_COMMITTER_* only if git config is present.
        """
```

### Branch strategy

Use `git worktree` to allow concurrent access to different branches of the same repo without multiple full clones.

**Layout:**

```
workspace/
├── lucabello/
│   └── grimoire/
│       ├── .bare/              # bare clone (shared object store)
│       ├── main/               # worktree for main branch
│       └── develop/            # worktree for develop branch
```

**Workflow:**

1. First time: `git clone --bare <url> .bare/`
   - **HTTPS** (default): `https://x-access-token:{token}@github.com/{owner}/{repo}.git`
   - **SSH** (if SSH keys configured): `git@github.com:{owner}/{repo}.git`
2. For each branch: `git worktree add ../{branch} {branch}` from the bare repo.
3. On sync: `git fetch origin` in the bare repo, then in each worktree: `git checkout {branch} && git reset --hard origin/{branch}`.

**Before each check/action** (`reset_workdir()`):
1. `git checkout {branch}` — ensure correct branch.
2. `git reset --hard origin/{branch}` — discard any local changes from previous action runs.
3. `git clean -fdx` — remove untracked files (build artifacts, temp files from scripts).
4. Return the workdir path.

This ensures:
- Minimal disk usage (shared object store).
- Concurrent read access to different branches (checks can run in parallel on different branches).
- Write access for actions (each worktree is an independent working directory).

### Git identity setup

**Only applied when `config.git` is not None.** If the `git` section is omitted from config, skip all identity/signing setup. Actions that need git identity (commit, push) should validate that `config.git` is present and fail with a clear error if not.

In the bare repo (applies to all worktrees):

```bash
git config user.name "{config.git.user.name}"
git config user.email "{config.git.user.email}"
```

If signing is configured:

```bash
git config commit.gpgsign true
git config gpg.format {ssh|openpgp}     # based on config.git.signing.format
git config user.signingkey {key_path}
```

**SSH signing:**
- Ensure `ssh-agent` is running (start if not).
- Add the configured key: `ssh-add {key_path}`.
- If `ssh_known_hosts` is configured, set `GIT_SSH_COMMAND="ssh -o UserKnownHostsFile={path}"`.

**GPG signing:**
- Import the key: `gpg --import {key_path}`.
- The GPG agent handles passphrase caching.

### Environment for subprocesses

`get_env()` returns a dict merged into the subprocess environment when running checks/actions:

```python
# Always present:
env = {
    "GH_TOKEN": config.github.token,
    "GITHUB_TOKEN": config.github.token,
}

# Only if config.git is set:
if config.git:
    env.update({
        "GIT_AUTHOR_NAME": config.git.user.name,
        "GIT_AUTHOR_EMAIL": config.git.user.email,
        "GIT_COMMITTER_NAME": config.git.user.name,
        "GIT_COMMITTER_EMAIL": config.git.user.email,
    })
    # If SSH configured:
    if config.git.ssh_known_hosts:
        env["GIT_SSH_COMMAND"] = f"ssh -o UserKnownHostsFile={config.git.ssh_known_hosts}"
```

## Acceptance Criteria

- [ ] Repos are cloned on first run, pulled on subsequent runs
- [ ] Worktrees are created for each observed branch
- [ ] Git identity is configured correctly (user.name, user.email)
- [ ] Signing is configured when specified (SSH or GPG)
- [ ] `get_workdir()` returns a valid path with the correct branch checked out; creates worktree if needed
- [ ] `reset_workdir()` leaves the workdir clean: correct branch, no local changes, no untracked files
- [ ] `get_env()` includes GH_TOKEN, GITHUB_TOKEN always; Git user env vars only when git config is present
- [ ] Git identity/signing setup is skipped when `config.git` is None
- [ ] Clone uses HTTPS with token by default; SSH when SSH keys are configured
- [ ] Multiple branches of the same repo can be accessed concurrently
- [ ] Tests use temporary directories and mock git operations
