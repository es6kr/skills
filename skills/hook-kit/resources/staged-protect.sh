#!/bin/bash
# staged-protect.sh: Prevent changes to already-staged files
# PreToolUse hook for Edit/Write - block edits to files that are already staged

# Extract the target file path from the environment variable
FILE_PATH=""
if [ -n "$CLAUDE_TOOL_INPUT" ]; then
  FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | jq -r '.file_path // empty' 2>/dev/null)
fi

# Pass through if there is no file path
[ -z "$FILE_PATH" ] && exit 0

# Pass through if not a git repository
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Check the list of staged files
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)
[ -z "$STAGED_FILES" ] && exit 0

# Convert the absolute path to a relative path
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
REL_PATH="${FILE_PATH#$REPO_ROOT/}"

# Check whether the file is staged
if echo "$STAGED_FILES" | grep -qxF "$REL_PATH"; then
  echo "[staged-protect] File '$REL_PATH' is already staged. Confirm via AskUserQuestion before editing."
  exit 0
fi

exit 0
