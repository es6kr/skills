#!/bin/bash
# Notify when UI-related files are modified
# Used with PostToolUse hook for Edit/Write tools

FILE_PATH="${CLAUDE_TOOL_INPUT_FILE_PATH:-${CLAUDE_TOOL_INPUT_file_path:-}}"

# Check if it's a UI-related file
if [[ "$FILE_PATH" == *.svelte ]] || \
   [[ "$FILE_PATH" == *.vue ]] || \
   [[ "$FILE_PATH" == *.tsx && "$FILE_PATH" == *component* ]] || \
   [[ "$FILE_PATH" == **/components/** ]]; then
  echo "UI_CHANGE_DETECTED: $FILE_PATH"
  echo "Consider running /ui-confirm to verify the changes in browser"
fi
