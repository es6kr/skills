#!/bin/bash
# PreToolUse:Edit|Write|Bash guard - a failed TaskCreate call must be retried.
# Delegates to the sibling .py. Fail-open if python3 is unavailable.
PY="$(command -v python3 || true)"
[ -z "$PY" ] && exit 0
exec "$PY" "$(dirname "$0")/block-taskcreate-error-unretried.py"
