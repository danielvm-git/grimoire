"""Entry point for BigBase deployment.

BigBase auto-detects Python apps and runs: uvicorn app:app --port $PORT
Grimoire is a package inside src/.
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from grimoire.app import create_app
    app = create_app()
except Exception:
    traceback.print_exc()
    from fastapi import FastAPI
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"error": "startup_failed"}

__all__ = ["app"]
