#!/bin/bash
# Commit Review Trigger Hook
# Detects successful git commit and signals Claude to invoke code-reviewer agent

TOOL_INPUT="${TOOL_INPUT:-}"
EXIT_CODE="${EXIT_CODE:-0}"
STDOUT="${STDOUT:-}"

# Only proceed if command succeeded
if [ "$EXIT_CODE" != "0" ]; then
  exit 0
fi

# Extract command from tool input
COMMAND=$(echo "$TOOL_INPUT" | jq -r '.command // empty' 2>/dev/null)

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Check if this is a git commit command
if [[ "$COMMAND" != *"git commit"* ]]; then
  exit 0
fi

# Extract commit hash from stdout (matches patterns like "[main abc1234]" or "[branch 1234567]")
COMMIT_SHA=$(echo "$STDOUT" | grep -oE '\[[^ ]+ [a-f0-9]+\]' | head -1 | grep -oE '[a-f0-9]{7,}')

if [ -z "$COMMIT_SHA" ]; then
  exit 0
fi

# Get project path
PROJECT_PATH=$(pwd)

echo "<commit-review-trigger>"
echo "Commit completed: $COMMIT_SHA"
echo "Project: $PROJECT_PATH"
echo "Launch code-reviewer agent with: Task tool, subagent_type='code-reviewer'"
echo "Prompt: \"Project path: $PROJECT_PATH\nCommit SHA: $COMMIT_SHA\nReview this commit.\""
echo "</commit-review-trigger>"

exit 0
