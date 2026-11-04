#!/bin/sh
echo "run.sh: starting (PORT=${PORT:-unset})" >&2
echo "run.sh: pwd=$(pwd)" >&2
ls -la .venv/bin/uvicorn >&2 2>&1 || true
exec .venv/bin/uvicorn grimoire.app:create_app --factory \
  --host 0.0.0.0 --port "${PORT:-8000}"
