---
bug_id: BUG-2026-11-09T000000
status: in-progress
severity: high
scope: web, deployment
title: Repo detail page is unreachable for repositories whose name starts with a dot
---

# BUG-2026-11-09T000000: `/repo/{owner}/.github` returns "404 page not found"

## Problem

- **Reported:** `https://grimoire.bigbase.click/repo/danielvm-git/.github` → `404 page not found`.
- **Actual:** The dashboard links every repo to `/repo/{owner}/{name}`. For a repo
  whose name starts with `.` (the tracked `danielvm-git/.github` repo), the public
  proxy rejects the request before it reaches Grimoire and answers with the Go
  `http.NotFound` body `404 page not found\n` (19 bytes, no HTML, no app header).
- **Expected:** the repo detail page renders, exactly like
  `/repo/danielvm-git/big-bolao` does today.

## Reproduction

```
$ curl -s -o /dev/null -w '%{http_code} %{size_download}\n' https://grimoire.bigbase.click/repo/danielvm-git/big-bolao
200 90170
$ curl -s -o /dev/null -w '%{http_code} %{size_download}\n' https://grimoire.bigbase.click/repo/danielvm-git/.github
404 19
$ curl -s https://grimoire.bigbase.click/repo/danielvm-git/.github | xxd | head -2
00000000: 3430 3420 7061 6765 206e 6f74 2066 6f75  404 page not fou
00000010: 6e64 0a                                  nd.
```

Discriminating probes (all `curl`, no headers):

| Path | Status | Body | Reached Grimoire? |
|---|---|---|---|
| `/repo/danielvm-git/big-bolao` | 200 | repo page | yes |
| `/repo/danielvm-git/foo.bar` | 404 | 7 448 B, `<title>Not Found — Grimoire</title>` | **yes** (app 404 template) |
| `/repo/danielvm-git/.github` | 404 | **19 B** `404 page not found` | **no** |
| `/repo/danielvm-git/%2Egithub` | 404 | 19 B `404 page not found` | no (proxy decodes, then rejects) |
| `/repo/danielvm-git/.github/` | 404 | 19 B `404 page not found` | no |
| `/repo?name=danielvm-git/.github` | 404 | **22 B** `{"detail":"Not Found"}` | **yes** (FastAPI, no such route yet) |

## Root cause

Two facts combined:

1. **Proxy guard (external):** the public edge rejects any request whose path
   contains a dot-prefixed segment. A dot *inside* a segment is fine
   (`foo.bar` reaches the app and renders Grimoire's own 404), so the guard is
   specifically on hidden/dot segments. Percent-encoding does not bypass it.
2. **URL shape (ours):** Grimoire puts the repository name in the path
   (`/repo/{owner}/{name}`), and `the-fleet` contains a repo literally named
   `.github`, so every link to it is generated in the rejected shape.

Grimoire never sees the request, so no app-side routing change to
`/repo/{owner}/{name}` can fix it — the dashboard must emit a URL the edge
accepts. The same shape problem exists for the repo page's own HTMX endpoints
(`/partials/repo-checks-status/{owner}/{name}`, `/partials/repo-checks-run/...`),
which would silently fail on that page.

## Fix approach

Add a second, proxy-safe URL form for the repo pages that carries the full name
in a **query parameter** (query strings are unaffected by the segment guard —
proved by the 22-byte FastAPI 404 above):

- `GET /repo?name={owner}/{repo}` → same handler as `/repo/{owner}/{name}`.
- `GET /partials/repo-checks-status?name=…` and `POST /partials/repo-checks-run?name=…`
  → same handlers as the path forms.
- A single URL builder, `repo_url(full_name)`, returns the query form when the
  repo name starts with `.`, and the existing path form otherwise. Templates use
  the builder everywhere, so ordinary repos keep their current URLs.

## TDD Fix Plan

1. **RED:**
   - `tests/test_web/test_router.py::test_repo_url_keeps_path_form_for_normal_repos`
   - `tests/test_web/test_router.py::test_repo_url_uses_query_form_for_dot_repos`
   - `tests/test_web/test_router.py::test_repository_detail_accepts_query_form`
   - `tests/test_web/test_router.py::test_repository_detail_query_form_404s_for_unknown_repo`
   - `tests/test_web/test_router.py::test_dashboard_links_dot_repos_with_query_form`
   - `tests/test_web/test_router.py::test_repo_checks_partials_accept_query_form`
2. **GREEN:** add the query-form routes, the builder, the Jinja global and the
   template call sites.
3. **verify:** `uv run pytest tests/test_web -q`

## Acceptance Criteria

- [ ] `GET /repo?name=danielvm-git/.github` renders the repo page (200) for a
      tracked repo whose name starts with a dot.
- [ ] Ordinary repos still render at `/repo/{owner}/{name}`; their links are
      unchanged.
- [ ] The dashboard, list, backlog, check-results and action-results views link
      dot-named repos through the query form.
- [ ] The repo page's "Run checks" button and its polling endpoint work for a
      dot-named repo (query-form partials).
- [ ] Unknown repo names 404 with the app's `not_found.html`, and a `name` that
      is not `owner/repo` 404s instead of crashing.
- [ ] `just check` green.

## Diagnosis (diagnose-root)

| Phase | Evidence |
|---|---|
| **Reproduce** | `/repo/danielvm-git/.github` → `404 page not found` (19 B, Go `http.NotFound`). Control `/repo/danielvm-git/big-bolao` → 200, 90 KB of Grimoire HTML. |
| **Isolate** | `/repo/danielvm-git/foo.bar` → app's own 404 template (7 448 B, `<title>Not Found — Grimoire</title>`), so a dot *inside* a segment passes. `.github`, `%2Egithub`, `%2egithub`, `.github/` and `.github?x=1` all return the 19-byte proxy body. `/repo?name=danielvm-git/.github` returns the 22-byte FastAPI 404 → query strings bypass the guard. |
| **Hypothesise** | Edge proxy blocks dot-prefixed path segments; the app never receives the request, so only the URL shape can be changed. |
| **Verify** | The guard is orthogonal to HTTP method and to the query string. Adding a query-form route and switching links for dot-named repos removes the blocked shape entirely (tests below). |

## Resolution

Fixed on `fix/dot-segment-repo-url`:

- `repo_url()`, `repo_checks_status_url()`, `repo_checks_run_url()` choose the form;
  ordinary repos are unchanged.
- `GET /repo?name=…`, `GET /partials/repo-checks-status?name=…`,
  `POST /partials/repo-checks-run?name=…` share the existing handlers through
  `_repository_page`, `_repo_checks_status`, `_repo_checks_run`.
- 8 regression tests, red before the change:
  `TestRepoUrlBuilder` (2) and `TestQueryFormRepoRoutes` (6) — including
  "malformed `name` 404s", "unknown repo 404s", and "matrix and list link the
  dot repo with `?name=`".
- `just check`: 736 passed; `pyright src`: 0 errors.

Note: the deployment must be redeployed before the live link changes; the
proxy guard itself is external and unchanged.
