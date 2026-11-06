# ADR-001: Modular Monolith with FastAPI and App Factory Pattern

## Status
Accepted

## Context
Grimoire aggregates fleet-wide GitHub repository statistics, provides real-time web dashboards, executes background health checks, and dispatches automated actions. We evaluated building a microservices architecture (separate GitHub collector, execution worker, and web frontend) versus a modular monolith.

## Decision
Adopt a modular monolith architecture built on Python 3.13+ and FastAPI using the application factory pattern (`create_app()`). Dependency injection across routers is achieved via module-level state setter functions (`set_checks_state()`, `set_actions_state()`).

## Consequences
- **Positive:** Single deployment unit, zero IPC network latency between scheduler and UI, simplified Docker containerization.
- **Negative:** Shared process memory requires strict concurrency limits (bounded via `asyncio.Semaphore(10)` for GitHub API and `Semaphore(5)` for check execution).

## Stress-Testing Evidence (grill-me)
- **Challenge:** Will module-level state setters cause race conditions during hot reload?
- **Resolution:** State injection happens strictly during the async `lifespan` startup phase before the ASGI server begins accepting HTTP requests. Verified through `tests/test_app.py` integration suite.
