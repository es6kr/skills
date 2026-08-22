#!/usr/bin/env bash
# PreToolUse hook (cross-platform: Claude Code + Antigravity):
# Block a consolidate AI Review Summary / Internal Code Review POST that cites a
# fabricated commit SHA or an inflated external-reviewer (Copilot) finding count.
#
# Rationale:
#   The Summary is the audit trail a merge decision is read against. A cited
#   `commit <sha>` that does not exist in the repo, or a "Copilot: N findings"
#   claim where the reviewer actually produced fewer, makes that record actively
#   misleading — a reader (or a future session) can approve a merge on a
#   fabricated basis. This guard verifies the two mechanically-checkable claims
#   at POST source. Case history: es6kr/skills PR #346 Summary cited commit
#   `4e7ee9e` (nonexistent) and inflated Copilot's 2 findings to "4 findings".
#
# Checks (BOTH fail open on any ambiguity — never false-block):
#   1. SHA existence — every `commit <7-40 hex>` cited must resolve. A local
#      `git cat-file -e <sha>^{commit}` HIT confirms existence offline; a miss is
#      inconclusive (the sha may be a real un-fetched remote commit), so the
#      authoritative check is `gh api repos/<owner>/<repo>/commits/<sha>`. Only a
#      definite 404/422 ("No commit found" / "Not Found") marks a sha fabricated.
#      No gh / no owner-repo / network error => that sha is UNKNOWN => skipped.
#   2. Copilot count — if the body states "Copilot ... N findings" and the PR's
#      actual Copilot review-comment count is < N, the count is inflated.
#
# Only acts on a consolidate-provenance comment (receiving-code-review /
# requesting-code-review link, or a <!-- consolidate: --> marker) so ad-hoc text
# is never touched.
#
# Cross-platform I/O contract (mirrors block-noncompliant-review-comment.sh):
#   - Claude Code:  stdin {tool_name, tool_input.command}; block = exit 2 + stderr.
#   - Antigravity:  stdin {toolCall.name, toolCall.args...}; block = stdout
#                   {"decision":"deny","reason":...} (+ exit 0).
#
# Bypass (explicit user override, per-command only — never session-wide):
#   ALLOW_SUMMARY_FABRICATED_CLAIMS=1 <command>

INPUT=$(cat)

# --- runtime detection + command extraction ---
CLAUDE_TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
AG_TOOL=$(echo "$INPUT" | jq -r '.toolCall.name // empty' 2>/dev/null)

RUNTIME=""
COMMAND=""
if [[ -n "$CLAUDE_TOOL" ]]; then
  RUNTIME="claude"
  [[ "$CLAUDE_TOOL" != "Bash" ]] && exit 0
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
elif [[ -n "$AG_TOOL" ]]; then
  RUNTIME="antigravity"
  [[ "$AG_TOOL" != "run_command" ]] && exit 0
  COMMAND=$(echo "$INPUT" | jq -r '.toolCall.args.command // .toolCall.args.CommandLine // (.toolCall.args | tostring) // empty' 2>/dev/null)
else
  exit 0
fi
[[ -z "$COMMAND" ]] && exit 0

# --- explicit override ---
if [[ "$ALLOW_SUMMARY_FABRICATED_CLAIMS" == "1" ]] || echo "$COMMAND" | grep -qE 'ALLOW_SUMMARY_FABRICATED_CLAIMS=1'; then
  exit 0
fi

# --- only act on a PR/issue comment or review POST ---
IS_POST=""
echo "$COMMAND" | grep -qE 'gh[[:space:]]+(pr|issue)[[:space:]]+comment' && IS_POST=1
echo "$COMMAND" | grep -qE 'gh[[:space:]]+pr[[:space:]]+review' && IS_POST=1
echo "$COMMAND" | grep -qE 'gh[[:space:]]+api[[:space:]].*(issues/[0-9]+/comments|pulls/[0-9]+/(comments|reviews))' && IS_POST=1
echo "$COMMAND" | grep -qE 'curl[[:space:]].*(issues/[0-9]+/comments|pulls/[0-9]+/(comments|reviews))' && IS_POST=1
[[ -z "$IS_POST" ]] && exit 0

# --- extract the body text (inline --body / --body-file / gh api body=@file / --input) ---
BODY=""
BODY="$(echo "$COMMAND" | grep -oE -- '(--body|-b)[[:space:]]+.*' | head -1)"
BF="$(echo "$COMMAND" | grep -oE -- '--body-file[[:space:]]+[^[:space:]]+' | awk '{print $2}')"
[[ -n "$BF" && -f "$BF" ]] && BODY="$BODY $(cat "$BF" 2>/dev/null)"
AF="$(echo "$COMMAND" | grep -oE -- '(--input[[:space:]]+[^[:space:]]+|body=@[^[:space:]]+)' | sed -E 's/^--input[[:space:]]+//; s/^body=@//')"
[[ -n "$AF" && -f "$AF" ]] && BODY="$BODY $(cat "$AF" 2>/dev/null)"
# Can't inspect the body (heredoc / env var / stdin) => do NOT block.
[[ -z "$BODY" ]] && exit 0

# --- only guard consolidate-provenance comments (Summary / Internal Review) ---
echo "$BODY" | grep -qE 'receiving-code-review|requesting-code-review|<!--[[:space:]]*consolidate:' || exit 0

# --- resolve owner/repo (for gh api lookups) ---
OWNER_REPO="$(echo "$COMMAND" | grep -oE -- '-R[[:space:]]+[^[:space:]]+/[^[:space:]]+' | awk '{print $2}' | head -1)"
[[ -z "$OWNER_REPO" ]] && OWNER_REPO="$(echo "$COMMAND" | grep -oE 'repos/[^/[:space:]]+/[^/[:space:]]+' | sed -E 's#repos/##' | head -1)"

# ===========================================================================
# Check 1 — fabricated commit SHA
# ===========================================================================
# Extract every hex token that follows the word "commit" (single or comma list).
SHAS="$(echo "$BODY" \
  | grep -oiE 'commit[s]?[[:space:]]+[0-9a-f]{7,40}([[:space:]]*,[[:space:]]*[0-9a-f]{7,40})*' \
  | grep -oiE '[0-9a-f]{7,40}' \
  | tr 'A-F' 'a-f' | sort -u)"

FABRICATED=""
if [[ -n "$SHAS" ]]; then
  IN_GIT=""
  git rev-parse --git-dir >/dev/null 2>&1 && IN_GIT=1
  for sha in $SHAS; do
    # 1a. local git confirms existence offline (fast positive)
    if [[ -n "$IN_GIT" ]] && git cat-file -e "${sha}^{commit}" 2>/dev/null; then
      continue
    fi
    # 1b. authoritative check via gh api — only a definite 404/422 is fabrication
    if command -v gh >/dev/null 2>&1 && [[ -n "$OWNER_REPO" ]]; then
      ERR="$(gh api "repos/$OWNER_REPO/commits/$sha" --jq '.sha' 2>&1 >/dev/null)"
      RC=$?
      if [[ $RC -eq 0 ]]; then
        continue   # exists
      elif echo "$ERR" | grep -qiE 'No commit found|Not Found|HTTP 404|HTTP 422|422 Unprocessable|Unprocessable Entity'; then
        FABRICATED="$FABRICATED $sha"
      fi
      # any other error (network/auth/rate-limit) => UNKNOWN => skip (fail open)
    fi
  done
fi
FABRICATED="$(echo "$FABRICATED" | tr -s ' ' | sed -E 's/^ //; s/ $//')"

# ===========================================================================
# Check 2 — inflated Copilot finding count
# ===========================================================================
COUNT_MSG=""
CLAIMED="$(echo "$BODY" | grep -iE 'copilot' | grep -oiE '[0-9]+[[:space:]]*findings?' | grep -oE '[0-9]+' | head -1)"
if [[ -n "$CLAIMED" ]] && command -v gh >/dev/null 2>&1 && [[ -n "$OWNER_REPO" ]]; then
  PRNUM="$(echo "$COMMAND" | grep -oE '(issues|pulls)/[0-9]+' | grep -oE '[0-9]+' | head -1)"
  [[ -z "$PRNUM" ]] && PRNUM="$(echo "$COMMAND" | grep -oE 'gh[[:space:]]+pr[[:space:]]+(comment|review)[[:space:]]+[0-9]+' | grep -oE '[0-9]+' | head -1)"
  if [[ -n "$PRNUM" ]]; then
    ACTUAL="$(gh api "repos/$OWNER_REPO/pulls/$PRNUM/comments" --jq '[.[] | select(.user.login | test("copilot"; "i"))] | length' 2>/dev/null)"
    if [[ "$ACTUAL" =~ ^[0-9]+$ ]] && (( CLAIMED > ACTUAL )); then
      COUNT_MSG="Reviewer Matrix claims Copilot produced ${CLAIMED} findings, but PR #${PRNUM} has only ${ACTUAL} actual Copilot review comment(s). Do not inflate or mis-attribute an external reviewer's findings — set the count to ${ACTUAL} and source the extra items to 'Internal Code Review'."
    fi
  fi
fi

# --- verdict ---
[[ -z "$FABRICATED" && -z "$COUNT_MSG" ]] && exit 0

REASON="Consolidate review comment contains an unverified factual claim."
[[ -n "$FABRICATED" ]] && REASON="$REASON Cited commit SHA(s) do not exist in ${OWNER_REPO:-the repo}: ${FABRICATED}. Verify every 'commit <sha>' with 'git cat-file -e <sha>' or 'gh api repos/<owner>/<repo>/commits/<sha>' before citing; remove or correct the fabricated SHA(s)."
[[ -n "$COUNT_MSG" ]] && REASON="$REASON $COUNT_MSG"

if [[ "$RUNTIME" == "antigravity" ]]; then
  printf '{"decision":"deny","reason":%s}\n' "$(printf '%s' "$REASON" | jq -Rs .)"
  exit 0
fi

cat >&2 <<EOF
[block-summary-fabricated-claims] DENIED: $REASON

Attempted command:
  $COMMAND

If this is genuinely user-approved (e.g. the SHA is on a branch this checkout
cannot see and you have verified it out-of-band), prefix per-command with:
  ALLOW_SUMMARY_FABRICATED_CLAIMS=1 <command>
EOF
exit 2
