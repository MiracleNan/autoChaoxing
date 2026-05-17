#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3.13}"
HOST="${SUPERSTAR_HOST:-127.0.0.1}"
PORT="${SUPERSTAR_PORT:-5050}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.13 is required. Set PYTHON_BIN to a Python 3.13 executable." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install -r requirements.txt

export SUPERSTAR_HOST="$HOST"
export SUPERSTAR_PORT="$PORT"

echo "Starting SuperStar Local at http://${HOST}:${PORT}"
python app.py
