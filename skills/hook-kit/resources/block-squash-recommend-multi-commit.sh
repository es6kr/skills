#!/usr/bin/env bash
# block-squash-recommend-multi-commit.sh — PreToolUse:AskUserQuestion gate.
#
# es6kr/skills uses semantic-release: commit-analyzer reads each commit's
# Conventional Commit type (feat/fix/...) to decide the version bump.
# Squash-merging a multi-commit PR collapses all of those types into one
# squash-commit message, silently losing the bump signal for every commit
# but the one chosen as the squash subject.
#
# Rule: ~/ghq/github.com/es6kr/.claude/rules/skills-publishing.md
#   "squash-merge recommendations are allowed only for single-commit PRs" —
#   before presenting a "Squash merge" option, verify the PR's actual commit count via
#   `gh pr view <N> --json commits`. If it isn't exactly 1, the option
#   must not be offered (or not offered as Recommended).
#
# This hook re-verifies independently of whatever the option text claims —
# it queries GitHub directly rather than trusting a commit-count string
# the assistant may have typed (or miscounted) into the description.
#
# History: failed-attempts.md class=squash-recommend-multi-commit
# (3+ recurrences before this hook existed; the hooks.json registration
# for this file existed since 2026-08-17 but the script itself was never
# actually written — this file closes that gap, 2026-08-20).

set -uo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "AskUserQuestion" ]] && exit 0

command -v gh >/dev/null 2>&1 || exit 0

ASK_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.question // ""),
  (.options[]? | (.label // ""), (.description // ""))
' 2>/dev/null)

[[ -z "$ASK_TEXT" ]] && exit 0

# Only fire when a squash-merge option is actually being proposed.
echo "$ASK_TEXT" | grep -qiE 'squash' || exit 0

# Extract every es6kr/skills PR number referenced in this ask.
PR_NUMBERS=$(echo "$ASK_TEXT" | grep -oE 'github\.com/es6kr/skills/pull/[0-9]+' | grep -oE '[0-9]+$' | sort -u)

[[ -z "$PR_NUMBERS" ]] && exit 0

VIOLATIONS=""
while IFS= read -r pr; do
  [[ -z "$pr" ]] && continue
  COUNT=$(timeout 8 gh pr view "$pr" -R es6kr/skills --json commits -q '.commits | length' 2>/dev/null)
  [[ -z "$COUNT" ]] && continue  # gh call failed/timed out — do not block on an inconclusive read
  if [[ "$COUNT" -ne 1 ]]; then
    VIOLATIONS="${VIOLATIONS}  - PR #${pr}: ${COUNT} commits (squash would collapse ${COUNT} Conventional Commit types into 1)\n"
  fi
done <<< "$PR_NUMBERS"

[[ -z "$VIOLATIONS" ]] && exit 0

{
  echo "DENIED: squash-merge option offered for a multi-commit es6kr/skills PR."
  echo
  echo "Why blocked:"
  printf "%b" "$VIOLATIONS"
  echo
  echo "Why this matters:"
  echo "  - semantic-release reads each commit's Conventional Commit type (feat/fix/...)"
  echo "    to decide the version bump. Squashing collapses all commits into one message,"
  echo "    silently losing the bump signal for every commit but the squash subject."
  echo
  echo "Required action (pick one before retrying):"
  echo "  1. Remove the squash option — offer a merge-commit option instead"
  echo "  2. If the commits should genuinely be 1 (already squashed locally),"
  echo "     re-verify with 'gh pr view <N> --json commits' and retry once the count is 1"
  echo "  3. Run commit-tidy to squash locally first, push, then re-offer squash-merge"
  echo
  echo "Reference: skills-publishing.md \"squash-merge recommendations are allowed only for single-commit PRs\""
} >&2
exit 2
