# Hand a problem to an agent

When a repository has something wrong with it, Grimoire can write the prompt for you so another agent (Claude Code, Codex, Copilot CLI, …) can fix it.

1. Open the repository detail page (`/repo/{owner}/{name}`).
2. In the **Pendencies** card, find the problem. Each row is a failing check, a failing workflow, a stale issue, or a stale pull request.
3. Click **Preview** to read the prompt, or **Copy prompt** to put it on your clipboard.
4. Paste it into your agent.

**Copy prompt for all** (top right) copies a single prompt covering every pendency, with errors first.

Workflow prompts also include when the failing run finished. Each prompt includes the repository, branch, what failed, the failing check output (last 2000 characters), the run or issue link, and a task description. Prompts are built from data Grimoire already has; nothing is sent to any external service.

## Run the checks for one repository

The **Checks** card on the repository page has a **Run checks** button. It runs every enabled check against that repository only, on all its tracked branches, and reloads the page when the run finishes. Checks that are already running somewhere else are skipped, and a notice tells you which ones.

Checks with a `schedule` only run on their cron, and the others run on each data refresh, so a freshly deployed instance can show them as **not run** until the next tick. The header counts these separately from passing checks. Use **Run checks** to fill them in right away.
