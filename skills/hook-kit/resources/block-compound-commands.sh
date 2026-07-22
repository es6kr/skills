#!/usr/bin/env bash
# PreToolUse hook: Block compound Bash commands
#
# Applied policy (HARD STOP — update this comment if policy changes):
#
# - permission_mode == "bypassPermissions" → not blocked (user has explicitly activated full-permission bypass mode; compound commands allowed)
# - permission_mode == any other value (default / plan / acceptEdits / auto / dontAsk) → compound commands blocked
# - permission_mode absent (field missing from hook input) → blocked by default (safety first)
#
# Why this exists:
# - Ralph autonomous loop runs with ALLOWED_TOOLS whitelist + permission_mode=default → blocked (PROMPT.md circuit breaker enforcement)
# - Regular interactive sessions also use default → blocked (forces user to review results step by step)
# - bypassPermissions is only entered when user explicitly activates it (Shift+Tab etc.) → user is assumed to have accepted compound-command side effects
#
# Blocked operators: 2>/dev/null, 2>&1, &&, ||, | (excluding the | that is part of ||)

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

PERMISSION_MODE=$(echo "$INPUT" | jq -r '.permission_mode // empty' 2>/dev/null)
if [[ "$PERMISSION_MODE" == "bypassPermissions" ]]; then
  exit 0
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$COMMAND" ]]; then
  exit 0
fi

BLOCKED=""

case "$COMMAND" in
  *"2>/dev/null"*) BLOCKED="2>/dev/null" ;;
esac

case "$COMMAND" in
  *"2>&1"*) BLOCKED="${BLOCKED:+$BLOCKED, }2>&1" ;;
esac

case "$COMMAND" in
  *"&&"*) BLOCKED="${BLOCKED:+$BLOCKED, }&&" ;;
esac

case "$COMMAND" in
  *"||"*) BLOCKED="${BLOCKED:+$BLOCKED, }||" ;;
esac

# pipe: | not inside ||
TEMP="${COMMAND//||/}"
case "$TEMP" in
  *"|"*) BLOCKED="${BLOCKED:+$BLOCKED, }|" ;;
esac

if [[ -n "$BLOCKED" ]]; then
  echo "DENIED: Compound command — operators: $BLOCKED. Split into separate Bash calls." >&2
  exit 2
fi

exit 0
