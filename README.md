# 🔮 Grimoire

<p align="center">
  <img src="logo.png" alt="Grimoire logo" width="200">
</p>

[![PyPI](https://img.shields.io/pypi/v/grimoire?label=PyPI&color=blue)](https://pypi.org/project/grimoire/)
[![GitHub Release](https://img.shields.io/github/v/release/lucabello/grimoire?label=GitHub&color=blue)](https://github.com/lucabello/grimoire/releases)
[![CI](https://github.com/lucabello/grimoire/actions/workflows/publish.yaml/badge.svg)](https://github.com/lucabello/grimoire/actions/workflows/publish.yaml)

> 📊 A self-hostable GitHub repository monitoring dashboard — track CI health, stale PRs/issues, and run automated checks & actions across your repos.

---

## ✨ Features

- 🔍 **Dashboard** — Compact, sortable view of all your repos' health at a glance
- ⚙️ **Checks** — Define custom scripts that run on a schedule against your repos
- 🚀 **Actions** — Automated remediation tasks (create PRs, fix issues, etc.)
- 🐳 **Docker-ready** — Single container, zero external dependencies
- 🔌 **REST API** — Full API with auto-generated OpenAPI docs at `/docs`

## 🚀 Getting Started

### With Docker (recommended)

```bash
# 1. Create your config file
cp config.yaml.example config.yaml
# Edit config.yaml with your GitHub token and repos

# 2. Run with docker-compose
docker compose up -d

# 3. Open the dashboard
open http://localhost:8000
```

### Local Development

```bash
# Prerequisites: Python 3.13+, uv, just

# 1. Clone and set up
git clone https://github.com/lucabello/grimoire.git
cd grimoire
uv sync

# 2. Configure
cp config.yaml.example config.yaml
# Edit config.yaml with your GitHub token and repos

# 3. Run in dev mode
just dev
```

## 📖 Configuration

Grimoire is configured via a single `config.yaml` file. See [`config.yaml.example`](config.yaml.example) for a fully commented reference, or read the [Configuration Reference](https://lucabello.github.io/grimoire/reference/configuration/).

## 📚 Documentation

Full documentation is available at **[lucabello.github.io/grimoire](https://lucabello.github.io/grimoire/)**.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and how to submit changes.

## 📄 License

See [LICENSE](LICENSE) for details.

