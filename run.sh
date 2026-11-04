#!/bin/sh
# Runtime entrypoint for BigBase deployments.
#
# The build step (`uv sync --frozen`) already created .venv in this directory.
# Starting the venv's uvicorn directly avoids `uv run`, which attempts to
# resolve/sync an environment at startup and can hang before the app binds.
set -eu

exec .venv/bin/uvicorn grimoire.app:create_app --factory \
  --host 0.0.0.0 --port "${PORT:-8000}"
