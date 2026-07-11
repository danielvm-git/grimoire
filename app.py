"""Entry point for BigBase deployment — re-exports the app factory.

BigBase auto-detects Python apps and runs uvicorn on the module root.
Grimoire is a package inside src/, so we expose the factory here.
"""

from grimoire.app import create_app

__all__ = ["create_app"]
