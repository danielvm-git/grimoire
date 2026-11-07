# Hand a problem to an agent

When a repository has something wrong with it, Grimoire can write the prompt for you so another agent (Claude Code, Codex, Copilot CLI, …) can fix it.

1. Open the repository detail page (`/repo/{owner}/{name}`).
2. In the **Pendencies** card, find the problem. Each row is a failing check, a failing workflow, a stale issue, or a stale pull request.
3. Click **Preview** to read the prompt, or **Copy prompt** to put it on your clipboard.
4. Paste it into your agent.

**Copy prompt for all** (top right) copies a single prompt covering every pendency, with errors first.

Each prompt includes the repository, branch, what failed, the failing check output (last 2000 characters), the run or issue link, and a task description. Prompts are built from data Grimoire already has; nothing is sent to any external service.
