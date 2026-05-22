"""CLI entrypoint for Grimoire."""

import sys


def main() -> None:
    """Run the Grimoire server."""
    import uvicorn

    uvicorn.run(
        "grimoire.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        loop="asyncio",
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
