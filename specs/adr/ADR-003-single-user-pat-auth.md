# ADR-003: Single-User Architecture with Personal Access Token (PAT) Authentication

## Status
Accepted

## Context
Grimoire interacts with the GitHub REST API to query private repositories and execute checks. We evaluated implementing OAuth2 multi-tenant authentication vs GitHub App vs Personal Access Token (PAT).

## Decision
Design Grimoire as a single-tenant, self-hosted application configured with a GitHub Personal Access Token (via `${GH_TOKEN}` or `${GITHUB_TOKEN}`). Multi-user RBAC and public Internet exposure without external proxy authentication are explicitly out of scope.

## Consequences
- **Positive:** Minimal configuration overhead; full token transparency; direct integration with developer workflows.
- **Negative:** Access privileges are tied directly to the token holder's GitHub permissions; deployment must be protected behind VPN or reverse proxy basic auth if hosted remotely.

## Stress-Testing Evidence (grill-me)
- **Challenge:** What prevents arbitrary command injection from script checks or token leakage?
- **Resolution:** Checks are strictly defined in local YAML config files managed by the operator, never accepted via unauthenticated HTTP endpoints. Subprocess execution caps output at 64KB and enforces strict 300s timeouts.
