---
bug_id: BUG-2026-11-09T000001
status: in-progress
severity: high
scope: config, github
title: Repository list is a hand-maintained static list, so tracked repos drift from the account
---

# BUG-2026-11-09T000001: Grimoire tracks 53 of the 58 repos on the account

## Problem

- **Reported:** "I have 58 repos, why is it fetching just 53?"
  (`https://github.com/danielvm-git?tab=repositories`)
- **Actual:** The dashboard tracks 53 repositories. `config.yaml` enumerates
  repositories one by one, so the tracked set is whatever was typed into that
  list and never reconciled with the account.
- **Expected:** the tracked set follows the account. Adding a repository on
  GitHub must make it appear in Grimoire without editing YAML, and deleting or
  renaming one must remove it.

## Measured state (2026-11-09)

| Source | Count |
|---|---|
| `config.yaml` `repo:` entries | **66** |
| Repos owned by `danielvm-git` (`/user/repos?affiliation=owner`) | **58** |
| Repos the dashboard actually tracks | **53** |
| GitHub API `404`s per refresh (`grimoire_github_api_requests_total{status="404"}`) | **13** |

66 config entries − 13 entries that no longer exist on GitHub = **53** tracked.
53 tracked + 5 existing repos never added to the config = **58** on GitHub.

Configured but deleted (13 — each costs an API call and a warning every refresh):
`add-tutorial-requests-site`, `big-robot`, `binance-trading-bot`, `ccxt-firebase-bot`,
`ccxt-trading-robot`, `desktop-tutorial`, `firebase-ccxt-bot-project`, `hello-world`,
`lick-hunter-server`, `marisales-robot`, `readme-portfolio-template`,
`semantic-release-baby`, `udacity`.

Existing but never configured (5): `big-gowrite`, `big-quiqui-v2`, `big-remote-control`,
`bigpowers-factory`, `pi`.

## Root cause

`GrimoireConfig.repositories` accepts only two source kinds
(`src/grimoire/config.py`): `StaticRepoSource` (`repo:`) and `TeamRepoSource`
(`team:`). There is no source that means "every repository this account owns",
so the only way to track a personal account is to maintain the list by hand.
The list is validated per entry at refresh time (`_resolve_static` → API `404` →
skipped), which hides both failure modes: stale entries vanish silently and new
repos are never discovered.

The `TeamRepoSource` proves the pattern exists for org teams
(`GET /orgs/{org}/teams/{slug}/repos`); a user account has no equivalent.

## Fix approach

Add a third source kind, symmetric with the team source:

```yaml
repositories:
  - user: "danielvm-git"        # every repo the account owns
    exclude: []                 # optional opt-outs
    workflows:                  # optional per-source workflow filter
      exclude: ["Dependabot *"]
```

- `GitHubClient.get_user_repos(user)` paginates `/user/repos?affiliation=owner`
  when the configured user is the token's own login (private repos included),
  otherwise `/users/{user}/repos?type=owner` (public only). The authenticated
  login is fetched once and cached.
- `_resolve_user()` mirrors `_resolve_team()`: skip excluded names, skip
  archived repos (with the existing tombstone), tag `source="user:<login>"`, and
  fall back to cached `user:` repos when the listing call fails or returns 304.
- `prune_removed_repos()` treats user sources like team sources (dynamic sets are
  authoritative only after resolution, which `prune_stale_data` already handles).
- `config.yaml` replaces its 66 static entries with `- user: "danielvm-git"`.
  The two per-repo `branches: [master]` overrides become unnecessary because both
  repos report `default_branch: master`.
- Docs: user source in `docs/user/reference/configuration.md`, spec 01 schema,
  spec 02 client/resolution.

## TDD Fix Plan

1. **RED:**
   - `tests/test_config.py::test_user_source_is_parsed`
   - `tests/test_config.py::test_repo_source_rejects_mixed_selectors`
   - `tests/test_github/test_client.py::test_get_user_repos_uses_authenticated_endpoint`
   - `tests/test_github/test_client.py::test_get_user_repos_uses_public_endpoint_for_other_users`
   - `tests/test_github/test_service.py::test_resolve_user_source_returns_every_repo`
   - `tests/test_github/test_service.py::test_resolve_user_source_skips_excluded_and_archived`
   - `tests/test_github/test_service.py::test_resolve_user_source_falls_back_to_cache_on_error`
2. **GREEN:** implement 1–4 above, then switch `config.yaml` to the user source.
3. **verify:** `uv run pytest tests/test_config.py tests/test_github -q`

## Acceptance Criteria

- [ ] `repositories: [{user: "x"}]` is a valid source; mixing `repo`/`team`/`user`
      on one entry is rejected.
- [ ] Discovery returns every owned repo (private included for the token owner),
      skips `exclude:` names and archived repos, and reuses cached `user:` repos
      when the API call fails or returns 304.
- [ ] `config.yaml` no longer enumerates repos; a refresh resolves all 58.
- [ ] `just check` green.
