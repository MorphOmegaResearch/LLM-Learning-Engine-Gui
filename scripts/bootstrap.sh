#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

"$PY" scripts/bootstrap.py "$@"

