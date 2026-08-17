#!/usr/bin/env bash
# Post a PR review as a dedicated review account, then restore the acting account.
# Implements the self-review account-switch sequence in one call:
#   register reviewer (acting) -> switch -> verify identity -> POST review -> restore
#
# Usage:
#   review-as.sh --repo <owner/repo> --pr <N> --reviewer <review-account> \
#                --acting <acting-account> --input <review-payload.json> [--skip-register]
#
# The payload is a pulls/reviews API JSON:
#   {"event": "APPROVE|REQUEST_CHANGES|COMMENT", "body": "...", "comments": [...]}
#
# The acting account is restored on EVERY exit path (trap EXIT), preventing
# review-account leakage into follow-up commits/comments.
set -euo pipefail

REPO="" PR="" REVIEWER="" ACTING="" INPUT="" SKIP_REGISTER=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --pr) PR="$2"; shift 2 ;;
    --reviewer) REVIEWER="$2"; shift 2 ;;
    --acting) ACTING="$2"; shift 2 ;;
    --input) INPUT="$2"; shift 2 ;;
    --skip-register) SKIP_REGISTER=1; shift ;;
    -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$REPO" || -z "$PR" || -z "$REVIEWER" || -z "$ACTING" || -z "$INPUT" ]]; then
  echo "missing required arg (--repo/--pr/--reviewer/--acting/--input)" >&2
  exit 2
fi
[[ -f "$INPUT" ]] || { echo "payload not found: $INPUT" >&2; exit 2; }

restore() {
  gh auth switch --user "$ACTING" >/dev/null 2>&1 || true
  local cur
  cur=$(gh api user --jq .login 2>/dev/null || echo "?")
  [[ "$cur" == "$ACTING" ]] || echo "WARN: acting account restore failed (current: $cur)" >&2
}
trap restore EXIT

if [[ $SKIP_REGISTER -eq 0 ]]; then
  gh api -X POST "repos/$REPO/pulls/$PR/requested_reviewers" \
    -f "reviewers[]=$REVIEWER" --jq '[.requested_reviewers[].login]'
fi

gh auth switch --user "$REVIEWER"
CUR=$(gh api user --jq .login)
if [[ "$CUR" != "$REVIEWER" ]]; then
  echo "ERROR: switch ineffective (current: $CUR) — use the command-scoped GH_TOKEN fallback from the self-review account-switch rule" >&2
  exit 1
fi

gh api "repos/$REPO/pulls/$PR/reviews" --method POST --input "$INPUT" \
  --jq '{id, user: .user.login, state}'
echo "OK — review posted as $REVIEWER (acting account restored on exit)"
