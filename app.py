"""Entry point for BigBase deployment.

BigBase auto-detects Python apps and looks for an `app` object.
Grimoire uses a factory pattern, so we instantiate the app at module level.
"""

from grimoire.app import create_app

app = create_app()

__all__ = ["app", "create_app"]
