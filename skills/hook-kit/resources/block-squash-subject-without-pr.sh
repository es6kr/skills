#!/usr/bin/env bash
# PreToolUse:Bash — Block `gh pr merge --squash` when subject is missing or lacks (#<PR>) suffix
#
# Trigger: Bash command `gh pr merge ... --squash ...`
# Action: Deny if either:
#   1. --subject option absent (subject must be explicit so the suffix can be enforced)
#   2. --subject value does not end with `(#<digits>)` suffix
#
# Background: failed-attempts.md "squash merge subject missing (#PR) suffix" (1st recurrence 2026-06-12).
# User explicit rule: the first line of a squash commit must end with the PR number (#XXX) + block even when --subject is absent.
# Rule body: github-flow/merge.md "Squash Merge" section HARD STOP.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$CMD" ]]; then
  exit 0
fi

# Match `gh pr merge` and `--squash` (also `-s` short form)
if ! echo "$CMD" | grep -qE '\bgh[[:space:]]+pr[[:space:]]+merge\b'; then
  exit 0
fi
if ! echo "$CMD" | grep -qE '(--squash|[[:space:]]-s[[:space:]]|[[:space:]]-s$)'; then
  exit 0
fi

# Use Python for accurate quoted-arg parsing (CMD passed via env, not stdin)
RESULT=$(SQUASH_HOOK_CMD="$CMD" python3 - <<'PY'
import os
import re
import shlex

cmd = os.environ.get("SQUASH_HOOK_CMD", "")

try:
    tokens = shlex.split(cmd)
except ValueError:
    print("PASS")
    raise SystemExit(0)

subject = None
i = 0
while i < len(tokens):
    tok = tokens[i]
    if tok == "--subject":
        if i + 1 < len(tokens):
            subject = tokens[i + 1]
        break
    if tok.startswith("--subject="):
        subject = tok[len("--subject="):]
        break
    i += 1

if subject is None:
    print("DENY_NO_SUBJECT")
    raise SystemExit(0)

if not re.search(r"\(#\d+\)\s*$", subject):
    print(f"DENY_BAD_SUFFIX:{subject}")
    raise SystemExit(0)

print("PASS")
PY
)

case "$RESULT" in
  PASS)
    exit 0
    ;;
  DENY_NO_SUBJECT)
    cat >&2 <<'MSG'
[~/.claude/hooks/block-squash-subject-without-pr.sh]: DENIED: `gh pr merge --squash` requires an explicit `--subject` argument.

Why blocked:
  - Subject must end with `(#<PR_NUMBER>)` suffix per github-flow/merge.md HARD STOP.
  - Without `--subject`, the suffix contract cannot be verified by this hook.
  - GitHub's native squash default also appends `(#N)`, but explicit `--subject` is required so the suffix is auditable in the merge command itself.

Required action:
  - Add `--subject "<prefix>: <description> (#<PR_NUMBER>)"` to the gh pr merge call.

Reference: failed-attempts.md "squash merge subject missing (#PR) suffix" (1st recurrence).
MSG
    exit 2
    ;;
  DENY_BAD_SUFFIX:*)
    SUBJ="${RESULT#DENY_BAD_SUFFIX:}"
    cat >&2 <<MSG
[~/.claude/hooks/block-squash-subject-without-pr.sh]: DENIED: squash subject does not end with \`(#<PR_NUMBER>)\` suffix.

Subject: ${SUBJ}

Why blocked:
  - Squash subject must end with \`(#<PR_NUMBER>)\` per github-flow/merge.md HARD STOP.
  - Matches GitHub's native squash default format.

Required action:
  - Append \` (#<PR_NUMBER>)\` to the --subject value (e.g., "ci: add npm-semantic-release workflow (#177)").

Reference: failed-attempts.md "squash merge subject missing (#PR) suffix" (1st recurrence).
MSG
    exit 2
    ;;
  *)
    # Unexpected output — pass to avoid false-blocking
    exit 0
    ;;
esac
