#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block a "squash merge" option that was not
# pre-verified against the PR's actual commit count.
#
# Trigger: an AskUserQuestion option's label or description mentions
#          squash-merge (e.g. "Squash and merge", "Squash merge")
# Action:  Deny unless that SAME option discloses the commit count it was
#          checked against (`commit count: N`), AND that disclosed count is
#          exactly 1. A squash option is never appropriate for a multi-commit
#          PR, even with an honest disclosure of the real count.
#
# Background: failed-attempts.md class "squash-recommend-multi-commit"
# (es6kr/skills PR #417, 4 recurrences) — squash was offered as a merge
# option without first checking `gh pr view <N> --json commits` for the
# PR's actual commit count. Squashing a multi-commit PR collapses distinct
# Conventional Commit types into one commit, corrupting release-please's
# per-type version bump. Rule: skills-publishing.md "squash-merge
# recommendation allowed only for single-commit PRs (HARD STOP)".
#
# This hook checks for the required DISCLOSURE (a deterministic, checkable
# textual signal), not the PR's actual commit count on GitHub — it has no
# way to know which PR is being discussed. The self-check this automates is:
# "did you run `gh pr view <N> --json commits` and write the result into the
# option before offering squash?"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

# Emit one record per option: "<option_label>\t<label + description>"
RECORDS=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? as $q |
  ($q.options // [])[] |
  [(.label // ""), ((.label // "") + " " + (.description // ""))] |
  @tsv
' 2>/dev/null)

if [[ -z "$RECORDS" ]]; then
  exit 0
fi

VIOLATIONS=()
while IFS=$'\t' read -r LABEL TEXT; do
  [[ -z "$LABEL" ]] && continue
  if ! echo "$TEXT" | grep -qiE 'squash'; then
    continue
  fi
  COUNT=$(echo "$TEXT" | grep -oiE 'commit count:[[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1)
  if [[ -z "$COUNT" ]]; then
    VIOLATIONS+=("$LABEL :: no commit-count disclosure found")
  elif [[ "$COUNT" != "1" ]]; then
    VIOLATIONS+=("$LABEL :: disclosed commit count is $COUNT, not 1 -- squash must not be offered at all")
  fi
done <<< "$RECORDS"

if [[ ${#VIOLATIONS[@]} -eq 0 ]]; then
  exit 0
fi

{
  echo "DENIED: AskUserQuestion offers a squash-merge option without a verified single-commit disclosure."
  echo ""
  for v in "${VIOLATIONS[@]}"; do
    echo "  - $v"
  done
  echo ""
  echo "Before offering a squash option, run:"
  echo "  gh pr view <N> --json commits -q '.commits | length'"
  echo "and write the result into the SAME option's description as:"
  echo "  commit count: N"
  echo ""
  echo "If N is not exactly 1, remove the squash option entirely -- do not offer it"
  echo "even with the count disclosed. Use a merge-commit option instead."
  echo ""
  echo "Reference: skills-publishing.md \"squash-merge recommendation allowed only for single-commit PRs (HARD STOP)\""
  echo "failed-attempts.md class: squash-recommend-multi-commit"
} >&2
exit 2
