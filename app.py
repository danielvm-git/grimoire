"""Entry point for BigBase deployment — fast health check + full app in background."""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from fastapi import FastAPI  # noqa: E402

# Minimal app — responds to health checks immediately.
# The full Grimoire app loads in the background and its routes
# (including the dashboard at /) are merged once ready.
app = FastAPI(title="Grimoire")


@app.get("/health")
async def health():
    return {"status": "ok"}


def _load_full_app() -> None:
    """Load the full Grimoire app in a background thread.

    Merges all routes from the real app into the running minimal app,
    skipping /health which is already defined above for fast startup.
    """
    try:
        from grimoire.app import create_app  # noqa: E402

        real = create_app()
        existing_paths = {route.path for route in app.routes}
        for route in real.routes:
            if route.path not in existing_paths:
                app.router.routes.append(route)
        print("Grimoire full app loaded", file=sys.stderr, flush=True)
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        print("Grimoire running in degraded mode", file=sys.stderr, flush=True)


t = threading.Thread(target=_load_full_app, daemon=True)
t.start()

if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
