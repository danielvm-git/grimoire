#!/bin/sh
# Setup script for installing external tools needed by checks/actions.
# This runs on every container start — keep commands idempotent.
#
# Examples:
#   pip install --no-cache-dir charmcraft
#   go install github.com/some/tool@latest
#   wget -qO /usr/local/bin/mytool https://example.com/mytool && chmod +x /usr/local/bin/mytool
#   apt-get update && apt-get install -y some-package

pip install --no-cache-dir charmcraft
