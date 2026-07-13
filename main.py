"""BigBase entrypoint — respects PORT env var set by BigBase.

BigBase runs `python3 app.py` directly (deploy.go:776).
This file exists for local development only.
"""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
