"""Entry point for BigBase deployment.

BigBase auto-detects Python apps and looks for an `app` object.
Grimoire is a package inside src/, so we add it to the path first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from grimoire.app import create_app  # noqa: E402

app = create_app()

__all__ = ["app", "create_app"]
