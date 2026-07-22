#!/usr/bin/env bash
# PostToolUse:Edit/Write — Notify when UI-related files are modified
#
# PostToolUse passes JSON on stdin (.tool_input.file_path); the
# CLAUDE_TOOL_INPUT_* env vars do not exist. stdout is debug-log only, so the
# notice is surfaced to the model via stderr + exit 2 per hook-kit/SKILL.md
# channel spec.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Edit|Write) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Check if it's a UI-related file
if [[ "$FILE_PATH" == *.svelte ]] || \
   [[ "$FILE_PATH" == *.vue ]] || \
   [[ "$FILE_PATH" == *.tsx && "$FILE_PATH" == *component* ]] || \
   [[ "$FILE_PATH" == */components/* ]]; then
  cat >&2 <<EOF
UI_CHANGE_DETECTED: $FILE_PATH
Consider running /ui-confirm to verify the changes in browser
EOF
  exit 2
fi
exit 0
