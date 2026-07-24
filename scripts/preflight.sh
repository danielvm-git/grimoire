#!/usr/bin/env bash
# story: e10s01
# Preflight — wraps the project gate (`just check` = format + lint + test).
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v just >/dev/null 2>&1; then
  echo "FAIL: just is required but not on PATH" >&2
  exit 1
fi

just check
