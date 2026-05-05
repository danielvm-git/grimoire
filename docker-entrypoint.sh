#!/bin/sh
set -e

# Run user-provided setup script if it exists (install external tools, etc.)
# Failures here are non-fatal — the app should still start even if tool
# installation fails; the affected checks will simply report errors.
if [ -f /app/data/setup.sh ]; then
    echo "Running data/setup.sh ..."
    sh /app/data/setup.sh || echo "WARNING: data/setup.sh exited with code $?"
fi

exec "$@"
