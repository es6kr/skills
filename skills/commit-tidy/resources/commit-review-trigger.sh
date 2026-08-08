#!/bin/bash
# Commit Review Trigger Hook
# Detects successful git commit and signals Claude to invoke code-reviewer agent

# PostToolUse hooks receive their payload as JSON on stdin, not as env vars.
INPUT=$(cat)

# Only act on Bash tool calls
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

# Extract the command that ran
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Check if this is a git commit command. Require "git commit" to appear as an actual
# command invocation (right after a command-boundary or the start of the string), not
# merely mentioned as substring text — e.g. `echo "run git commit later"` or
# `git log --grep="git commit"` must NOT trigger this hook.
if ! grep -qE '(^|[;&|`]|\bthen\b)[[:space:]]*git[[:space:]]+commit([[:space:]]|$)' <<< "$COMMAND"; then
  exit 0
fi

# Bash tool_response exposes stdout/stderr (no exit_code field); a failed commit
# won't print the "[branch <sha>]" line, so the SHA extraction below is the success gate.
STDOUT=$(echo "$INPUT" | jq -r '.tool_response.stdout // empty' 2>/dev/null)

# Extract commit hash from stdout. Handle "[main abc1234]" and multi-word refs like
# "[detached HEAD abc1234]" / "[main (root-commit) abc1234]".
COMMIT_SHA=$(echo "$STDOUT" | grep -oE '\[[^]]+ [a-f0-9]{7,}\]' | head -1 | grep -oE '[a-f0-9]{7,}')

if [ -z "$COMMIT_SHA" ]; then
  exit 0
fi

# Get project path
PROJECT_PATH=$(pwd)

echo "<commit-review-trigger>"
echo "Commit completed: $COMMIT_SHA"
echo "Project: $PROJECT_PATH"
echo "Launch code-reviewer agent with: Task tool, subagent_type='code-reviewer'"
# printf %b (not `echo`) so the embedded \n sequences render as real line breaks —
# plain `echo` treats \n as literal backslash-n in POSIX-mode bash (xpg_echo off).
printf '%b\n' "Prompt: \"Project path: $PROJECT_PATH\nCommit SHA: $COMMIT_SHA\nReview this commit.\""
echo "</commit-review-trigger>"

exit 0
