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

# Pick the first interpreter that actually runs. A bare `command -v python3`
# check is not enough on Windows, where `python3` resolves to a non-functional
# Microsoft Store App Execution Alias stub (exits non-zero / opens the Store).
# Probe each candidate with a trivial program so the broken stub is skipped in
# favour of a working `python`. CI runners (real python3) match the first probe.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "check-hangul.sh: no working python interpreter found on PATH" >&2
  exit 2
fi

exec "$PY" "$SCRIPT_DIR/check-hangul.py" "$@"
