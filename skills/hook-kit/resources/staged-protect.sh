#!/bin/bash
# staged-protect.sh: Prevent accidental edits/writes in working trees with active staged work
# PreToolUse hook for Edit/Write - warns when editing files in a repository with active staged changes

# Extract the target file path from the environment variable
FILE_PATH=""
if [ -n "$CLAUDE_TOOL_INPUT" ]; then
  FILE_PATH=$(echo "$CLAUDE_TOOL_INPUT" | jq -r '.file_path // empty' 2>/dev/null)
fi

# Pass through if there is no file path
[ -z "$FILE_PATH" ] && exit 0

# Exempt if target is inside .worktrees/
case "$FILE_PATH" in
  .worktrees/*|*/.worktrees/*) exit 0 ;;
esac

# Resolve directory of target file
FILE_DIR=$(dirname "$FILE_PATH" 2>/dev/null)
[ -z "$FILE_DIR" ] && FILE_DIR="."

# Pass through if target is not inside a git repository
git -C "$FILE_DIR" rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Exempt if target path is ignored by git (.gitignore)
git -C "$FILE_DIR" check-ignore -q "$FILE_PATH" 2>/dev/null && exit 0

# Check if the target repository has any staged changes
if git -C "$FILE_DIR" diff --cached --quiet 2>/dev/null; then
  # Repository is clean of staged changes -> allow without warning
  exit 0
fi

REPO_ROOT=$(git -C "$FILE_DIR" rev-parse --show-toplevel 2>/dev/null)

# Check whether the target file itself has staged changes
if ! git -C "$FILE_DIR" diff --cached --quiet -- "$FILE_PATH" 2>/dev/null; then
  echo "[staged-protect] File '$FILE_PATH' is already staged in '$REPO_ROOT'. Confirm via AskUserQuestion before editing."
  exit 0
fi

# Target file is not staged, but repository has other staged files (worktree isolation violation risk)
echo "[staged-protect] Warning: Repository at '$REPO_ROOT' has staged changes. Modifying '$FILE_PATH' while unrelated changes are staged may mix commits. Consider using an isolated git worktree."
exit 0

