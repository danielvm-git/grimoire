# AGENTS.md

Instructions for AI agents working on this codebase.

## Orientation

Read `docs/00-overview.md` first — it has the tech stack, project structure, module dependency graph, config format, and REST API summary.

## Specs

Every module has a spec in `docs/`, numbered by dependency order. Each spec is the authoritative reference for its module: it includes all models, file paths, API routes, and acceptance criteria.

- **Read the relevant spec before modifying a module.**
- When adding a feature that spans modules, update all affected specs.
- If a new independent module is needed, create a new numbered spec following the same format.
- Specs are self-contained, agent-optimized, and ordered so module N only depends on modules < N.

## Workflow for new features

Before implementing a new feature, identify which modules and specs are affected. Present this list to the user for approval before writing any code. This includes:

- Which spec files will be read and potentially updated.
- Which source modules will be modified or created.
- Whether new tests are needed and where they belong.

## Commands

Run `just --list` to see all available recipes. The key one is:

```bash
just check    # format + lint + test — run this after every change
```

After any code change, run `just check` and verify zero failures before considering the change complete.

## Testing

Tests mirror the source structure under `tests/`. Key conventions:

- All tests are async — no manual `@pytest.mark.asyncio` needed.
- GitHub API mocking uses `respx` — never make real API calls in tests.
- Web route tests populate the in-memory cache via `update_cache()` in a fixture.
- Filesystem-touching tests use `tmp_path` for isolation.

When modifying or adding functionality, add or update corresponding tests in the matching `tests/` subdirectory.

## Database

We are in active development — there is no need for schema migrations. When changing the SQLite schema (adding/removing columns or tables), just update the SQLModel definitions and delete `grimoire.db`. It will be recreated on the next run.

## Style

- Keep code simple, modular, and testable.
- Only comment where behavior is non-obvious.
- Use `TYPE_CHECKING` imports to avoid circular dependencies between modules.
- Module-level mutable state uses setter functions (e.g., `set_checks_state()`) for dependency injection and testability.

