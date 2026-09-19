#!/usr/bin/env bash
# Stop event — Detect a `/rename` candidate list that omits the
# `<model>-<slug>-<sessid8>` schema suffix when the session shows evidence of
# being wrap-up-adjacent, per session/rename.md "Wrap-up / findability variant".
#
# This is deliberately a SEPARATE hook from block-cleanup-missing-rename.sh
# (which only checks that a `/rename ` token exists at all, and only fires on
# literal cleanup/session-end report markers). This hook adds two things that
# hook lacked:
#   1. Schema-FORMAT validation (does a candidate actually end in -<8 hex>?),
#      not just token presence.
#   2. Broader trigger scope — a STANDALONE `/session rename` request (no
#      /cleanup wording at all) still counts as wrap-up-adjacent if a Stop
#      "cleanup trigger" fired earlier in this session, or /fix or /fa
#      (which delegates to cleanup:retrospect) was invoked earlier — the
#      candidate array's default should already reflect that per rename.md.
#
# Background: failed-attempts.md "session-rename-schema-missing-sessid8-suffix"
# class, 4th recurrence — 1st/2nd occurrences omitted or demoted the schema
# form; 3rd occurrence escalated status to hook-pending but no hook existed
# yet; 4th occurrence was a standalone /session rename request (no /cleanup
# wording in the response at all) where the session had an earlier Stop
# "cleanup trigger" fire plus an /fa (retrospect) call, both of which
# rename.md's own "adjacent to a session wrap-up" clause already covers —
# this hook makes that judgment mechanical instead of relying on re-deriving
# "was this turn wrap-up-adjacent?" from memory every time.

if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

INPUT=$(cat)

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

RESPONSE=$(echo "$INPUT" | jq -r '
  .response // .transcript // .assistant_message // empty
' 2>/dev/null)

if [[ -z "$RESPONSE" ]] && [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  RESPONSE=$(tail -50 "$TRANSCRIPT_PATH" | jq -rs '([.[] | select(.type=="assistant")] | last) as $m | ($m.message.content[]?.text? // empty)' 2>/dev/null)
fi

if [[ -z "$RESPONSE" ]]; then
  exit 0
fi

# Nothing to check if there is no /rename candidate in this response at all.
if ! echo "$RESPONSE" | grep -qE '/rename[[:space:]]'; then
  exit 0
fi

# --- Wrap-up adjacency detection (session-wide, not just this response) ---
WRAPUP_ADJACENT=0

# Signal A: this response itself reads as a cleanup/session-end report.
if echo "$RESPONSE" | grep -qiE '(^|[[:space:]])/cleanup|cleanup run|cleanup wrap-up|cleanup complete|cleanup pass|cleanup finished|Session Ended|Session Cleanup|session-end report'; then
  WRAPUP_ADJACENT=1
fi

if [[ "$WRAPUP_ADJACENT" -eq 0 ]] && [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  # Signal B: a Stop "cleanup trigger" hook feedback fired earlier in this
  # session (even if the actual cleanup ceremony was then skipped via the
  # context-threshold gate — the fire itself is the adjacency signal).
  if grep -qE 'cleanup trigger' "$TRANSCRIPT_PATH" 2>/dev/null; then
    WRAPUP_ADJACENT=1
  fi
fi

if [[ "$WRAPUP_ADJACENT" -eq 0 ]] && [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  # Signal C: /fix or /fa (which delegates to cleanup:retrospect) was invoked
  # earlier in this session — both are session-mistake-recording activity of
  # the same wrap-up-flavored character as /cleanup itself.
  if grep -qE '"skill"[[:space:]]*:[[:space:]]*"(cleanup|fix|es6kr:fa|es6kr:fix)"' "$TRANSCRIPT_PATH" 2>/dev/null; then
    WRAPUP_ADJACENT=1
  fi
fi

if [[ "$WRAPUP_ADJACENT" -eq 0 ]]; then
  exit 0
fi

# --- Schema check: does at least one candidate match <model>-<slug>-<sessid8>? ---
# Extract the text on each `/rename ...` line (strip everything up to and
# including "/rename" plus following whitespace; also strip a trailing
# backtick/quote/paren if the candidate was wrapped in a code span).
CANDIDATES=$(echo "$RESPONSE" | grep -oE '/rename[[:space:]]+[^`'"'"'"]+' | sed -E 's#^/rename[[:space:]]+##')

SCHEMA_OK=0
while IFS= read -r cand; do
  [[ -z "$cand" ]] && continue
  if echo "$cand" | grep -qE '^[A-Za-z0-9]+-[A-Za-z0-9-]+-[0-9a-f]{8}[[:space:]]*$'; then
    SCHEMA_OK=1
    break
  fi
done <<< "$CANDIDATES"

if [[ "$SCHEMA_OK" -eq 1 ]]; then
  exit 0
fi

cat <<'EOF'
{
  "decision": "block",
  "reason": "This session shows wrap-up-adjacency signals (a Stop 'cleanup trigger' fired earlier, and/or /fix or /fa was invoked earlier this session, and/or this response itself reads as a cleanup/session-end report) but the /rename candidates just presented are all bare single-slugs with no <model>-<slug>-<sessid8> schema form. Per session/rename.md's 'Wrap-up / findability variant' section, wrap-up-adjacent turns must place the <model>-<slug>-<sessid8> form FIRST/default among the candidates -- not just include it as an afterthought. Re-derive <sessid8> via session/id.md's source-priority procedure and re-present the candidate list with the schema form first. See failed-attempts.md 'session-rename-schema-missing-sessid8-suffix' for the recurrence history this hook exists to stop."
}
EOF
exit 2
