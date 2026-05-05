# Getting started

This tutorial walks you through installing Grimoire and monitoring your first repositories.

## Before you begin

You need:

- A **GitHub personal access token** with `repo` scope (read access to the repos you want to monitor)
- **Docker** (recommended) or Python 3.13+ with [uv](https://docs.astral.sh/uv/)

## Step 1 — Create your configuration

```bash
curl -O https://raw.githubusercontent.com/lucabello/grimoire/main/config.yaml.example
cp config.yaml.example config.yaml
```

Open `config.yaml` and set your token and at least one repository:

```yaml
github:
  token: "${GITHUB_TOKEN}"   # or a literal token

repositories:
  - repo: "your-org/your-repo"
```

## Step 2 — Start Grimoire

=== "Docker Compose"

    ```bash
    curl -O https://raw.githubusercontent.com/lucabello/grimoire/main/docker-compose.yml
    export GITHUB_TOKEN="ghp_your_token_here"
    docker compose up -d
    ```

=== "Local (development)"

    ```bash
    git clone https://github.com/lucabello/grimoire.git
    cd grimoire
    uv sync
    cp config.yaml.example config.yaml
    # Edit config.yaml
    just dev
    ```

## Step 3 — Open the dashboard

Navigate to [http://localhost:8000](http://localhost:8000).

Grimoire fetches data from the GitHub API immediately on startup. The dashboard populates as data arrives — each repository card shows a `fetched_at` timestamp so you know how fresh the data is.

## Step 4 — Explore the interface

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Sortable overview of all repos' health |
| Backlog | `/backlog` | Prioritised list of problems across repos |
| Checks | `/checks` | Custom validation scripts and their results |
| Actions | `/actions` | Automated remediation tasks and run logs |
| API docs | `/docs` | Interactive Swagger UI |

## What's next

- [Write your first check](../how-to/write-a-check.md) to enforce a standard across repos
- Read the [configuration reference](../reference/configuration.md) for all available options
- [Deploy to production](../how-to/deploy.md) with Docker and a reverse proxy
