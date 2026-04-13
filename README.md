# {{project_name}}

[![PyPi Release](https://img.shields.io/pypi/v/{{project_name}}?label=PyPi&color=blue)](https://pypi.org/project/{{project_name}}/)
[![GitHub Release](https://img.shields.io/github/v/release/lucabello/{{project_name}}?label=GitHub&color=blue)](https://github.com/lucabello/{{project_name}}/releases)
[![Publish to PyPi](https://github.com/lucabello/{{project_name}}/actions/workflows/publish.yaml/badge.svg)](https://github.com/lucabello/{{project_name}}/actions/workflows/publish.yaml)
![Commits Since Release](https://img.shields.io/github/commits-since/lucabello/{{project_name}}/latest?label=Commits%20since%20last%20release&color=darkgreen)

---

You should start by substituting `{{project_name}}` and `{{project_description}}` everywhere.

In order to register the package to PyPi, do the following:
1. Go to: https://pypi.org/manage/account/publishing/
2. Add a **pending publisher**, with:
   - Workflow name: `publish.yaml`
   - Environment name: `pypi`
3. Create a `pypi` environment in your GitHub repository:
