#!/usr/bin/env bash
# collect.sh — Collect all GitHub PR details, reviews, checks, and comments in one run.
# Usage: collect.sh <repo> <pr_number> [account]
#   e.g. collect.sh daegunsoftDev/turborepo-web 412 daegunjhy

set -euo pipefail

REPO="${1:?usage: collect.sh <repo> <pr_number> [account]}"
PR="${2:?usage: collect.sh <repo> <pr_number> [account]}"
ACCOUNT="${3:-}"

# Inject GH_TOKEN if account is specified to work around multi-account keyring bugs
if [[ -n "$ACCOUNT" ]]; then
  echo "INFO: Pinning GitHub account: $ACCOUNT" >&2
  export GH_TOKEN="$(gh auth token --user "$ACCOUNT")"
fi

echo "=================================================="
echo "PR COLLECTION SUMMARY: PR #$PR on $REPO"
echo "=================================================="
echo ""

# 1. Copilot billing (Step 2.4 signals)
echo "=== Copilot Billing Status ==="
if gh api /user/copilot_billing &>/dev/null; then
  echo "User Copilot billing: Enabled/Active"
else
  echo "User Copilot billing: Inactive or No Access"
fi

OWNER="${REPO%%/*}"
if gh api "/orgs/$OWNER/copilot/billing" &>/dev/null; then
  echo "Org ($OWNER) Copilot billing: Enabled/Active"
else
  echo "Org ($OWNER) Copilot billing: Inactive or No Access"
fi
echo ""

# 2. PR Metadata (head, base, mergeable)
echo "=== PR Metadata ==="
gh pr view "$PR" -R "$REPO" --json headRefName,headRefOid,baseRefName,mergeable,isCrossRepository,headRepositoryOwner --jq '
  "Branch: \(.headRefName)\nHead SHA: \(.headRefOid)\nBase Branch: \(.baseRefName)\nMergeable: \(.mergeable)\nCross Repo: \(.isCrossRepository)\nHead Owner: \(.headRepositoryOwner.login)"
'
echo ""

# 3. CodeRabbit and expected reviewer counts
echo "=== Review Counts ==="
REVIEWS_JSON=$(gh pr view "$PR" -R "$REPO" --json reviews)
echo "$REVIEWS_JSON" | jq -r '
  "CodeRabbit reviews: \([.reviews[] | select(.author.login | test("coderabbit"; "i"))] | length)",
  "daegunjhy reviews: \([.reviews[] | select(.author.login | test("daegunjhy"; "i"))] | length)"
'
echo ""

# 4. Files changed
echo "=== Files Changed ==="
gh pr view "$PR" -R "$REPO" --json files --jq '.files[] | "\(.path) (+\(.additions)/-\(.deletions))"'
echo ""

# 5. PR Body
echo "=== PR Body ==="
gh pr view "$PR" -R "$REPO" --json body --jq '.body'
echo ""

# 6. PR Checks
echo "=== PR Checks ==="
gh pr checks "$PR" -R "$REPO" 2>&1 || echo "No checks reported or error querying checks."
echo ""

# 7. Inline review comments
echo "=== Inline Review Comments ==="
gh api "repos/$REPO/pulls/$PR/comments" --jq '.[] | "\(.user.login) @ \(.path):\(.line // .original_line) :: \(.body[0:200])"' || echo "No inline comments found."
echo ""

# 8. All Reviews (bot + non-bot)
echo "=== All Reviews ==="
echo "$REVIEWS_JSON" | jq -r '.reviews[] | "\(.author.login) [\(.state)] :: \(.body[0:150])"' || echo "No reviews found."
echo ""

# 9. Member/Owner/Collaborator comments
echo "=== Member/Owner/Collaborator Comments ==="
gh pr view "$PR" -R "$REPO" --json comments --jq '
  .comments[] | select(.authorAssociation == "MEMBER" or .authorAssociation == "OWNER" or .authorAssociation == "COLLABORATOR") | 
  "\(.author.login) (\(.authorAssociation)) :: \(.body[0:150])"
' || echo "No comments found."
echo ""

# 10. CodeRabbit walkthrough comment
echo "=== CodeRabbit Walkthrough Comment ==="
gh pr view "$PR" -R "$REPO" --json comments --jq '
  [.comments[] | select(.author.login | test("coderabbit"; "i"))] | last | .body
' | head -n 80 || echo "No CodeRabbit comments found."
echo ""
