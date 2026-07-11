"""BigBase entrypoint — respects PORT env var set by BigBase."""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "app:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
    )
