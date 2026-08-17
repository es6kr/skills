#!/bin/bash
# PreToolUse:Edit|Write guard - /wip register-before-execute.
# Delegates to the sibling .py. Korean registration-verb variants are loaded
# from data/hangul-patterns.regex (git-ignored; English-only fallback keeps the
# guard functional without locale data). Fail-open if python is unavailable.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
export HG_WIP_REGISTER_VERBS="${HG_WIP_REGISTER_VERBS:-add|write|create|draft|record|register}"

PY="$(command -v python3 || true)"
[ -z "$PY" ] && exit 0
exec "$PY" "$(dirname "$0")/block-wip-register-before-execute.py"
