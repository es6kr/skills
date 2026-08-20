#!/bin/bash
# PreToolUse:Edit|Write guard - /wip register-before-execute.
# Lives next to its .py implementation in the skill it gates (see CLAUDE.md
# "within-marketplace" placement rule). Korean registration-verb variants load
# from hook-kit/data/hangul-patterns.regex (git-ignored; the English-only
# fallback keeps the guard functional without locale data).
#
# Fails OPEN when either python3 or the sibling .py is unavailable. A missing
# dependency must degrade this guard, never block every Edit/Write in the
# session - that is exactly what happened when the .py moved away from the
# wrapper and the wrapper exec'd a path that no longer existed.
HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
export HG_WIP_REGISTER_VERBS="${HG_WIP_REGISTER_VERBS:-add|write|create|draft|record|register}"

PY="$(command -v python3 || true)"
[ -z "$PY" ] && exit 0
IMPL="$(dirname "$0")/block-wip-register-before-execute.py"
[ -f "$IMPL" ] || exit 0
exec "$PY" "$IMPL"
