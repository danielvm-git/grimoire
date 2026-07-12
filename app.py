"""Entry point for BigBase deployment."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
print("Grimoire starting...", file=sys.stderr, flush=True)

from fastapi import FastAPI  # noqa: E402

# Minimal app that starts immediately for health check
app = FastAPI(title="Grimoire")


@app.get("/")
async def root():
    return {"status": "ok", "name": "Grimoire Dashboard"}


# Try to start the full app in the background
async def start_real_app():
    try:
        from grimoire.app import create_app

        real = create_app()
        # Copy routes from real app
        for route in real.routes:
            app.router.routes.append(route)
        print("Grimoire full app loaded", file=sys.stderr, flush=True)
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        print("Running in degraded mode", file=sys.stderr, flush=True)


# Schedule async startup
import threading  # noqa: E402


def _start():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(start_real_app())


t = threading.Thread(target=_start, daemon=True)
t.start()
