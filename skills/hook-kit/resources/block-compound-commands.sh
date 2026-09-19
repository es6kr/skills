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
#
# Quote-context masking (fix for a recurring false-positive class — see
# failed-attempts.md "block-compound-commands.sh flags operators inside
# quoted strings"): a literal pipe/&&/|| inside a single- or double-quoted
# string (e.g. grep -E "A|B") is not a shell operator — it is scanned only
# after masking quoted regions, so detection matches actual shell syntax
# rather than raw substring presence.

# mask_quotes: replace the *content* of single/double-quoted regions (and
# backslash-escaped characters outside quotes) with '_' so operator-shaped
# substrings inside them can no longer match, while leaving unquoted shell
# syntax (including the quote delimiters themselves) untouched for the
# case-pattern checks below. Backslash-escapes inside double quotes are
# consumed as a pair so an escaped quote (\") does not end the region early.
mask_quotes() {
  local s="$1"
  local out=""
  local c
  local i=0
  local len=${#s}
  local in_s=0
  local in_d=0
  while (( i < len )); do
    c="${s:i:1}"
    if (( in_s )); then
      if [[ "$c" == "'" ]]; then in_s=0; out+="'"; else out+="_"; fi
      (( i++ )); continue
    fi
    if (( in_d )); then
      if [[ "$c" == "\\" ]]; then
        out+="__"; i=$(( i + 2 )); continue
      elif [[ "$c" == '"' ]]; then
        in_d=0; out+='"'
      else
        out+="_"
      fi
      (( i++ )); continue
    fi
    case "$c" in
      "'") in_s=1; out+="'" ;;
      '"') in_d=1; out+='"' ;;
      '\') out+="__"; i=$(( i + 2 )); continue ;;
      *) out+="$c" ;;
    esac
    (( i++ ))
  done
  printf '%s' "$out"
}

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

MASKED="$(mask_quotes "$COMMAND")"

BLOCKED=""

case "$MASKED" in
  *"2>/dev/null"*) BLOCKED="2>/dev/null" ;;
esac

case "$MASKED" in
  *"2>&1"*) BLOCKED="${BLOCKED:+$BLOCKED, }2>&1" ;;
esac

case "$MASKED" in
  *"&&"*) BLOCKED="${BLOCKED:+$BLOCKED, }&&" ;;
esac

case "$MASKED" in
  *"||"*) BLOCKED="${BLOCKED:+$BLOCKED, }||" ;;
esac

# pipe: | not inside ||
TEMP="${MASKED//||/}"
case "$TEMP" in
  *"|"*) BLOCKED="${BLOCKED:+$BLOCKED, }|" ;;
esac

if [[ -n "$BLOCKED" ]]; then
  echo "DENIED: Compound command — operators: $BLOCKED. Split into separate Bash calls." >&2
  exit 2
fi

exit 0
