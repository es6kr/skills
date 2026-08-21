#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block a squash-merge option for an es6kr/skills PR
# whose commit count is not exactly 1.
#
# Trigger: AskUserQuestion contains an option (label or description) mentioning
#          "squash" (case-insensitive) AND a github.com/es6kr/skills/pull/<N> URL.
# Action: look up the PR's real commit count via `gh pr view`. Deny when it is
#         not exactly 1.
#
# Why: es6kr/skills uses semantic-release, which assigns minor/patch bumps by
# commit type (feat/fix). Squash-merging a multi-commit PR collapses those
# distinct commit-type signals into a single squash commit, silently breaking
# the bump matrix. See skills-publishing.md "squash-merge recommendation only
# allowed for single-commit PRs" and failed-attempts.md "squash-recommend-multi-commit".

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

# Collect every (label + description) pair across all questions/options.
OPTION_TEXTS=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]?.options[]? |
  ((.label // "") + "\n" + (.description // ""))
' 2>/dev/null)

if [[ -z "$OPTION_TEXTS" ]]; then
  exit 0
fi

if ! echo "$OPTION_TEXTS" | grep -qiE 'squash'; then
  exit 0
fi

PR_URL=$(echo "$OPTION_TEXTS" | grep -oE 'github\.com/es6kr/skills/pull/[0-9]+' | head -1)
if [[ -z "$PR_URL" ]]; then
  # A squash mention without an es6kr/skills PR URL isn't this hook's concern
  # (either a different repo, or ask-guard's PR-URL-matching guard handles it).
  exit 0
fi

PR_NUM="${PR_URL##*/}"

if ! command -v gh >/dev/null 2>&1; then
  exit 0
fi

COMMIT_COUNT=$(gh pr view "$PR_NUM" -R es6kr/skills --json commits -q '.commits | length' 2>/dev/null)

if [[ -z "$COMMIT_COUNT" ]]; then
  # Could not determine commit count (auth/network issue) — don't false-block.
  exit 0
fi

if [[ "$COMMIT_COUNT" != "1" ]]; then
  {
    echo "DENIED: squash-merge option proposed for es6kr/skills PR #$PR_NUM, which has $COMMIT_COUNT commits (not 1)."
    echo ""
    echo "Why blocked:"
    echo "  - es6kr/skills uses semantic-release, which bumps versions by commit type"
    echo "    (feat/fix). Squashing a multi-commit PR collapses that type information"
    echo "    into one commit, silently corrupting the bump matrix."
    echo ""
    echo "Required action:"
    echo "  Remove the squash option. Offer a non-squash merge (preserves each commit),"
    echo "  or a 'commit-tidy first, then squash' option instead."
    echo ""
    echo "Reference: skills-publishing.md 'squash-merge recommendation only allowed for single-commit PRs'"
    echo "           failed-attempts.md 'squash-recommend-multi-commit'"
  } >&2
  exit 2
fi

exit 0
