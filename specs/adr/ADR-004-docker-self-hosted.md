# ADR-004: Self-Hosted Docker Deployment with Jinja2 + HTMX Frontend

## Status
Accepted

## Context
The user interface requires real-time status updates without introducing a heavy JavaScript node-based build toolchain (React, Next.js, Webpack).

## Decision
Package Grimoire as a self-contained Docker container (`python:3.13-slim` base) serving server-rendered Jinja2 templates augmented with HTMX partials and Tailwind/DaisyUI CSS. Deployment is platform-agnostic (Docker, Docker Compose, or standalone systemd).

## Consequences
- **Positive:** Zero frontend build pipeline (`npm run build` is not needed); single deployment artifact; sub-second initial render speeds.
- **Negative:** Complex client-side dynamic behaviors rely on server-side partial rendering via HTMX triggers (`HX-Trigger`).

## Stress-Testing Evidence (grill-me)
- **Challenge:** How does the UI handle long-running check runs without freezing the browser?
- **Resolution:** HTMX polling partials (`/api/checks/{slug}/status`) swap status badges asynchronously until the run completes.
