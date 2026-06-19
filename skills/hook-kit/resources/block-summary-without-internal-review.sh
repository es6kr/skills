#!/usr/bin/env bash
# PreToolUse:Bash — Block `## AI Review Summary` POST when Internal Code Review comment is missing
#
# Trigger: Bash command posting a PR comment whose body contains `## AI Review Summary`
# Action: Deny if same PR has CodeRabbit walkthrough_start marker but no `## Internal Code Review` comment
#
# Background: failed-attempts.md "Internal Code Review comment posting missing" (5+ recurrences) — comment posting missing.
# pr-review.md Step 3.5.3 requires Internal Code Review comment posted BEFORE Step 7 Summary.
# Rule strengthening alone failed; this hook automates the Step 3.5 gate.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Detect PR comment POST patterns (precision: require explicit POST markers)
# Without this, jq selector queries like `jq '.body | contains("AI Review Summary")'`
# trigger false positives. POST requires either --body/--body-file on `gh pr comment`,
# or -X POST / --method POST / --input on `gh api .../comments`.
IS_POST=0

# gh pr comment: always POST (creates comment), but require --body or --body-file
# to exclude commands that just mention the literal text without posting.
if [[ "$COMMAND" == *"gh pr comment"* ]]; then
  if echo "$COMMAND" | grep -qE -- '(--body[= ]|--body-file[= ])'; then
    IS_POST=1
  fi
fi

# gh api .../comments with explicit POST flag (-X POST, --method POST, --input, -f body=, -F body=)
if [[ "$IS_POST" -eq 0 ]]; then
  if echo "$COMMAND" | grep -qE 'gh api.*(/issues/[0-9]+/comments|issues/comments).*(\-X[[:space:]]+POST|\-\-method[[:space:]]+POST|\-\-input[= ]|\-f[[:space:]]+body=|\-F[[:space:]]+body=)'; then
    IS_POST=1
  fi
fi

if [[ "$IS_POST" -eq 0 ]]; then
  exit 0
fi

# Detect Summary body content — inline or referenced file
HAS_SUMMARY=0
if echo "$COMMAND" | grep -qE '## AI Review Summary|AI Review Summary'; then
  HAS_SUMMARY=1
fi

# Check --body-file argument for Summary content
BODY_FILE=$(echo "$COMMAND" | grep -oE -- '--body-file[= ][^ ]+|--input[= ][^ ]+' | head -1 | sed -E 's/^--(body-file|input)[= ]//')
if [[ -n "$BODY_FILE" && -f "$BODY_FILE" ]]; then
  if grep -qE '## AI Review Summary|AI Review Summary' "$BODY_FILE" 2>/dev/null; then
    HAS_SUMMARY=1
  fi
fi

if [[ "$HAS_SUMMARY" -eq 0 ]]; then
  exit 0
fi

# Extract PR number and repo
PR_NUM=$(echo "$COMMAND" | grep -oE 'gh pr comment[[:space:]]+[0-9]+' | grep -oE '[0-9]+' | head -1)
if [[ -z "$PR_NUM" ]]; then
  PR_NUM=$(echo "$COMMAND" | grep -oE 'issues/[0-9]+/comments' | grep -oE '[0-9]+' | head -1)
fi

if [[ -z "$PR_NUM" ]]; then
  # PR number unresolvable — skip (don't block, but also can't verify)
  exit 0
fi

REPO=$(echo "$COMMAND" | grep -oE -- '-R[[:space:]]+[^[:space:]]+' | awk '{print $2}' | head -1)
if [[ -z "$REPO" ]]; then
  REPO=$(echo "$COMMAND" | grep -oE 'repos/[^/]+/[^/]+/' | head -1 | sed 's|^repos/||; s|/$||')
fi

if [[ -z "$REPO" ]]; then
  # Repo unresolvable — skip
  exit 0
fi

# Fetch existing comments
COMMENTS_JSON=$(GH_TOKEN="$(gh auth token --user daegunjhy 2>/dev/null)" gh api "repos/$REPO/issues/$PR_NUM/comments" 2>/dev/null)

if [[ -z "$COMMENTS_JSON" ]]; then
  # API failure — skip (don't block on infrastructure issue)
  exit 0
fi

# Check 1: CodeRabbit walkthrough_start marker present?
HAS_WALKTHROUGH=0
if echo "$COMMENTS_JSON" | jq -e '[.[] | select(.body | contains("<!-- walkthrough_start -->"))] | length > 0' >/dev/null 2>&1; then
  HAS_WALKTHROUGH=1
fi

# Check 2: Internal Code Review already posted — issue comment OR review-medium?
# internal.md "Medium decision": when inline targets exist (line-specific Critical/Important),
# the Internal Review is posted via the reviews API (gh api .../pulls/N/reviews) with comments[],
# NOT as an issue comment. So scan BOTH media before declaring it missing.
HAS_INTERNAL_REVIEW=0
if echo "$COMMENTS_JSON" | jq -e '[.[] | select(.body | startswith("## Internal Code Review"))] | length > 0' >/dev/null 2>&1; then
  HAS_INTERNAL_REVIEW=1
fi
# review-medium check (pulls/N/reviews array)
if [[ "$HAS_INTERNAL_REVIEW" -eq 0 ]]; then
  REVIEWS_JSON=$(GH_TOKEN="$(gh auth token --user daegunjhy 2>/dev/null)" gh api "repos/$REPO/pulls/$PR_NUM/reviews" 2>/dev/null)
  if [[ -n "$REVIEWS_JSON" ]] && echo "$REVIEWS_JSON" | jq -e '[.[] | select(.body | startswith("## Internal Code Review"))] | length > 0' >/dev/null 2>&1; then
    HAS_INTERNAL_REVIEW=1
  fi
fi

# Block condition: walkthrough exists (Step 3.5 trigger met) + Internal Review missing + Summary about to be posted
if [[ "$HAS_WALKTHROUGH" -eq 1 && "$HAS_INTERNAL_REVIEW" -eq 0 ]]; then
  cat >&2 <<MSG
DENIED: Posting AI Review Summary without Internal Code Review comment.

PR: $REPO#$PR_NUM
State:
  - CodeRabbit walkthrough_start marker: PRESENT (Step 3.5 trigger met)
  - Internal Code Review comment: MISSING
  - About to POST: AI Review Summary

pr-review.md Step 3.5.3 requires Internal Code Review comment posted BEFORE Step 7 Summary.
The "single combined comment" pattern (Internal fallback only) is deprecated — always 2 comments.

Required action before retry:
  1. Post Internal Code Review comment first:
     gh pr comment $PR_NUM -R $REPO --body-file /tmp/internal-review.json
     (with body starting "## Internal Code Review — [requesting-code-review](...)")
  2. Verify posting:
     gh api repos/$REPO/issues/$PR_NUM/comments --jq '.[] | select(.body | startswith("## Internal Code Review"))'
  3. Then re-issue this Summary POST command

Reference: failed-attempts.md "Internal Code Review comment posting missing" (Internal Code Review comment posting missing, 5+ recurrences).
MSG
  exit 2
fi

exit 0
