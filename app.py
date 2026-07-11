"""Entry point for BigBase deployment.

BigBase auto-detects Python apps and runs uvicorn on `app:app`.
Grimoire is a package inside src/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from grimoire.app import create_app
    app = create_app()
except Exception:
    # Fallback: minimal FastAPI app for health check
    from fastapi import FastAPI
    app = FastAPI(title="Grimoire (fallback)")

    @app.get("/")
    async def root():
        return {"status": "starting", "message": "Grimoire is initializing"}

__all__ = ["app"]
