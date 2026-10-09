#!/usr/bin/env bash
# PostToolUse:Bash Hook — Rebase Conflict Residue Guard
#
# Detects when 'git rebase --continue' succeeds but leaves git's auto-generated
# '± Conflicts:' or '# Conflicts:' block uncleaned in the commit message.
#
# Regression guard for class=rebase-conflict-residue-in-commit-message-leak.
#
# Contract:
#   - Receives tool payload JSON on stdin
#   - Exits 0 on non-Bash tools, non-rebase commands, or clean commit messages
#   - Exits 2 if HEAD commit message contains rebase conflict residue

set -u

# Support direct test mode if invoked with --test
if [[ "${1:-}" == "--test" ]]; then
  echo "check-rebase-conflict-residue.sh: self-test mode OK"
  exit 0
fi

INPUT="$(cat)"

# Only act on Bash tool calls
TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)"
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

# Extract the executed command
COMMAND="$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"
if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Check if the command includes 'git rebase --continue'
# Accommodates prefixes like 'GIT_EDITOR=true', subshell boundaries, and chained commands (&&, ;, |)
if ! grep -qE '(^|[;&|`]|\bthen\b)[[:space:]]*([A-Za-z0-9_]+=[^[:space:]]+[[:space:]]+)*git[[:space:]]+rebase[[:space:]]+--continue([[:space:]]|$)' <<< "$COMMAND"; then
  exit 0
fi

# Ensure we are inside a git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

# Inspect the commit message of HEAD
COMMIT_MSG="$(git log -1 --format='%B' 2>/dev/null || true)"
if [[ -z "$COMMIT_MSG" ]]; then
  exit 0
fi

# Check for conflict residue marker
if grep -qE '^[#±][[:space:]]*Conflicts:' <<< "$COMMIT_MSG"; then
  COMMIT_INFO="$(git log -1 --format='%h %s' 2>/dev/null || echo 'HEAD')"
  cat >&2 <<EOF
<rebase-conflict-residue-detected>
ERROR: Rebase conflict residue detected in commit message of ${COMMIT_INFO}:
--------------------------------------------------------------------------------
$(grep -E '^[#±][[:space:]]*Conflicts:' -A 5 <<< "$COMMIT_MSG")
--------------------------------------------------------------------------------
HARD STOP: The commit message contains auto-generated '± Conflicts:' residue.
Please sanitize the commit message immediately before continuing:
    git commit --amend
</rebase-conflict-residue-detected>
EOF
  exit 2
fi

exit 0
