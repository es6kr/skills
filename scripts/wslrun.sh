#!/bin/bash
# wslrun.sh — shell wrapper for wslrun.py
set -euo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
    exec python3 "$SELF_DIR/wslrun.py" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$SELF_DIR/wslrun.py" "$@"
else
    echo "Error: Python interpreter not found." >&2
    exit 1
fi
