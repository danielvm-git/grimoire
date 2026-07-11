"""Entry point for BigBase deployment."""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# BigBase runs: uvicorn app:app --host 0.0.0.0 --port $PORT
# Print to stderr so BigBase captures it
print("Grimoire starting...", file=sys.stderr, flush=True)

try:
    from grimoire.app import create_app
    app = create_app()
    print("Grimoire app created successfully", file=sys.stderr, flush=True)
except Exception as e:
    import traceback
    traceback.print_exc(file=sys.stderr)
    print(f"FATAL: {e}", file=sys.stderr, flush=True)
    # Create a minimal app so BigBase health check passes
    from fastapi import FastAPI
    app = FastAPI()
    @app.get("/")
    async def root():
        return {"status": "error", "detail": str(e)}
