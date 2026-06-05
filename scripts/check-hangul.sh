#!/usr/bin/env bash
# check-hangul.sh — Thin wrapper that delegates to check-hangul.py.
#
# Historically this script invoked `grep -rPc '[Hangul]'` directly, which made
# its verdict depend on whatever `grep` happened to be on PATH. On macOS, a
# common ugrep wrapper that adds `--ignore-files` produced false negatives
# (Korean text shipping to GitHub uncaught). The Python implementation removes
# that dependency entirely.
#
# Usage is unchanged:
#   bash check-hangul.sh [skills-parent-dir]
#   bash check-hangul.sh <skill-dir1> [skill-dir2] ...
#
# Exit codes (unchanged):
#   0 = all clean
#   1 = Korean text found

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer python3; fall back to python so this works on minimal environments
# (CI runners always have python3; this fallback is for older user setups).
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "check-hangul.sh: python3 not found on PATH" >&2
  exit 2
fi

exec "$PY" "$SCRIPT_DIR/check-hangul.py" "$@"
