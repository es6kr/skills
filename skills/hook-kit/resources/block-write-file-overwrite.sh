#!/usr/bin/env bash
# PreToolUse:write_to_file — Block task.md Overwrite (Overwrite: true) when task.md already exists
#
# Trigger: write_to_file tool call targeting a task.md file with Overwrite: true when the file exists
# Action: Deny with guidance to use replace_file_content / multi_replace_file_content or incremental append.
#
# Recurrences: failed-attempts.md [class] task-md-overwrite-loss (count=3, status=hook-pending -> hook-active)
#
# Cross-platform I/O contract (es6kr/skills issue #265 Phase 2 pilot):
#   The tool this guard targets (write_to_file) is itself an Antigravity-native
#   name, but the ORIGINAL version of this script only ever read Claude Code's
#   {tool_name, tool_input} shape and only ever blocked via stderr+exit 2 -
#   meaning it silently never fired on a real Antigravity payload
#   ({toolCall.name, toolCall.args}), despite nominally targeting Antigravity's
#   own tool. Both shapes are now read; Antigravity blocks via stdout
#   {"decision":"deny","reason":...} + exit 0 (same script registered in
#   ~/.claude/settings.json AND ~/.gemini/config/hooks.json; precedent:
#   consolidate/resources/block-noncompliant-review-comment.sh).
#   NOTE (unverified): exact Antigravity write_to_file arg key names
#   (TargetFile/Overwrite casing) are guessed from this repo's existing
#   wip/antigravity.md docs, not confirmed live - verify + adjust in a real
#   Antigravity session.

INPUT=$(cat)

CLAUDE_TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
AG_TOOL=$(echo "$INPUT" | jq -r '.toolCall.name // empty' 2>/dev/null)

RUNTIME=""
TARGET_FILE=""
OVERWRITE=""
if [[ -n "$CLAUDE_TOOL" ]]; then
  RUNTIME="claude"
  if [[ "$CLAUDE_TOOL" != "write_to_file" && "$CLAUDE_TOOL" != "default_api:write_to_file" ]]; then
    exit 0
  fi
  TARGET_FILE=$(echo "$INPUT" | jq -r '.tool_input.TargetFile // .tool_input.target_file // empty' 2>/dev/null)
  OVERWRITE=$(echo "$INPUT" | jq -r '.tool_input.Overwrite // .tool_input.overwrite // false' 2>/dev/null)
elif [[ -n "$AG_TOOL" ]]; then
  RUNTIME="antigravity"
  if [[ "$AG_TOOL" != "write_to_file" ]]; then
    exit 0
  fi
  TARGET_FILE=$(echo "$INPUT" | jq -r '.toolCall.args.TargetFile // .toolCall.args.target_file // .toolCall.args.path // empty' 2>/dev/null)
  OVERWRITE=$(echo "$INPUT" | jq -r '.toolCall.args.Overwrite // .toolCall.args.overwrite // false' 2>/dev/null)
else
  exit 0
fi

REASON="Overwriting existing task.md with (Overwrite: true) is strictly prohibited (HARD STOP). Overwriting task.md wipes out existing pending/in_progress tasks from previous turns, causing context loss (failed-attempts.md [class] task-md-overwrite-loss, 3rd recurrence). Read existing tasks from $TARGET_FILE first (view_file), then use replace_file_content or multi_replace_file_content to incrementally append or update tasks. Never initialize task.md with write_to_file (Overwrite: true) when it already exists. Reference: GEMINI.md Task Checklist Registration Policy (HARD STOP)."

# Check if target is a task.md file
if [[ "$TARGET_FILE" == *"task.md"* ]]; then
  if [[ "$OVERWRITE" == "true" && -f "$TARGET_FILE" ]]; then
    if [[ "$RUNTIME" == "antigravity" ]]; then
      printf '{"decision":"deny","reason":%s}\n' "$(printf '%s' "$REASON" | jq -Rs .)"
      exit 0
    fi
    {
      echo "DENIED: $REASON"
      echo ""
      echo "Target File: $TARGET_FILE"
    } >&2
    exit 2
  fi
fi

exit 0
