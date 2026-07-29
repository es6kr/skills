#!/usr/bin/env bash
# PreToolUse hook (cross-platform: Claude Code + Antigravity):
# Block a garbage "review-flavored" PR/issue comment or review POST that bypasses
# the consolidate skill.
#
# Rationale:
#   The consolidate skill mandates that any AI-review response be posted with a
#   provenance-bearing title:
#     - AI Review Summary:    "## AI Review Summary — [receiving-code-review](...)"
#     - Internal Code Review: "## Internal Code Review — [requesting-code-review](...)"
#   A compliant comment therefore always contains one of the skill links
#   "receiving-code-review" / "requesting-code-review" (or an explicit
#   "<!-- consolidate:verified -->" marker). A garbage comment — e.g. an ad-hoc
#   "## CodeRabbit findings — verification notes" dumped straight onto a PR,
#   skipping collect -> internal -> classify -> post (consolidate SKILL.md
#   Don't/Do #5) — carries none of these signals. This guard denies such a POST
#   at source so the agent routes through consolidate.
#
# Cross-platform I/O contract:
#   - Claude Code:  stdin {tool_name, tool_input.command}; block = exit 2 + stderr.
#   - Antigravity:  stdin {toolCall.name, toolCall.args...}; block = stdout
#                   {"decision":"deny","reason":...} (+ exit 0).
#   The same script emits BOTH so it works registered in ~/.claude/settings.json
#   AND ~/.gemini/config/hooks.json.
#
#   NOTE (unverified): the exact Antigravity run_command arg key is not confirmable
#   from a Claude Code session. This script tries "command" / "CommandLine" and
#   falls back to the stringified args object. Verify + adjust in a real
#   Antigravity session.
#
# Bypass (explicit user override, per-command only — never session-wide):
#   ALLOW_NONCOMPLIANT_REVIEW_COMMENT=1 <command>

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
if [[ "$ALLOW_NONCOMPLIANT_REVIEW_COMMENT" == "1" ]] || echo "$COMMAND" | grep -qE 'ALLOW_NONCOMPLIANT_REVIEW_COMMENT=1'; then
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
# Can't inspect the body (heredoc / env var / stdin) → do NOT block (avoid false positive).
[[ -z "$BODY" ]] && exit 0

# --- is this a review-flavored comment? (keyword cluster, FP-guarded) ---
# Require a review-tool/review mention AND a findings/severity cluster so casual
# mentions ("CodeRabbit flagged X, will fix") do not trip the guard.
REVIEW_FLAVORED=""
if echo "$BODY" | grep -qiE 'coderabbit|copilot|code[ -]?review|review summary' \
   && echo "$BODY" | grep -qiE 'finding|verif|nitpick|actionable|inline comment|(^|[^a-z])(major|minor|critical)([^a-z]|$)'; then
  REVIEW_FLAVORED=1
fi
[[ -z "$REVIEW_FLAVORED" ]] && exit 0

# --- does it carry the consolidate provenance signal? ---
if echo "$BODY" | grep -qE 'receiving-code-review|requesting-code-review|<!--[[:space:]]*consolidate:'; then
  exit 0   # compliant — routed through consolidate
fi

# --- DENY (dual-emit) ---
REASON="Review-flavored PR/issue comment lacks the consolidate provenance signal (a receiving-code-review / requesting-code-review link, or a <!-- consolidate: --> marker). Route the review through the consolidate skill (collect -> internal -> classify -> post) instead of posting an ad-hoc review comment. See consolidate SKILL.md Don't/Do #5."

if [[ "$RUNTIME" == "antigravity" ]]; then
  printf '{"decision":"deny","reason":%s}\n' "$(printf '%s' "$REASON" | jq -Rs .)"
  exit 0
fi

cat >&2 <<EOF
[block-noncompliant-review-comment] DENIED: $REASON

Attempted command:
  $COMMAND

If this is a genuinely user-approved ad-hoc comment, prefix per-command with:
  ALLOW_NONCOMPLIANT_REVIEW_COMMENT=1 <command>

Otherwise run the consolidate skill so the Summary / Formal Review is posted with
its mandatory provenance title.
EOF
exit 2
