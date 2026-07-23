#!/usr/bin/env bash
# UserPromptSubmit hook: when the user message contains a task-completion keyword,
# inject a system-reminder guiding "verify + delete the task".

USER_MSG="${CLAUDE_USER_PROMPT:-}"

# Locale detection patterns live in git-ignored data/ (Korean + English). The hook
# carries an English-only fallback so the PUBLIC copy works without the data file.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
[ -f "$HG_DATA_FILE" ] && . "$HG_DATA_FILE"
WIP_COMPLETE_KEYWORDS="${WIP_COMPLETE_KEYWORDS:-finished|completed|done in another session|handled it|already (did|handled)}"
WIP_TASKREF_PATTERN="${WIP_TASKREF_PATTERN:-(#[0-9]+|task [0-9]+)}"

# Completion keyword pattern
if echo "$USER_MSG" | grep -qiE "$WIP_COMPLETE_KEYWORDS"; then
  # Try to extract task refs (#N, task N, etc.)
  TASK_REFS=$(echo "$USER_MSG" | grep -oE "$WIP_TASKREF_PATTERN" | head -5)

  if [ -n "$TASK_REFS" ]; then
    cat <<EOF
<system-reminder>
[WIP Task Complete Detect] The user mentioned task completion: ${TASK_REFS}
Verify the task via TaskGet, then delete it with TaskUpdate(status: "deleted").
If the user's message also contains other questions/instructions, handle those too.
</system-reminder>
EOF
  else
    cat <<EOF
<system-reminder>
[WIP Task Complete Detect] The user mentioned task completion.
Check current tasks with TaskList and delete completed ones via TaskUpdate(status: "deleted").
If the user's message also contains other questions/instructions, handle those too.
</system-reminder>
EOF
  fi
fi
