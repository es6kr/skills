#!/usr/bin/env bash
# Stop event — Detect a cleanup/session-end completion report that includes
# the "Session ID:" identity line but omits the accompanying `/rename`
# recommendation (2-3 candidates) required by cleanup/run.md Step 5's
# "Session identity (mandatory)" row.
#
# Trigger: assistant response contains cleanup-completion or session-end markers
#          AND a "Session ID:" line
# Detection: no `/rename ` command token anywhere in the same response.
# Locale-specific marker variants live in data/hangul-patterns.regex
# (git-ignored — this repo is PUBLIC, English-only source).
# Action: emit reminder via stdout (non-blocking read, but exit 2 blocks Stop
#         and injects context for the next turn).
#
# Background: failed-attempts.md "cleanup-procedure" class, 11th recurrence —
# the Session-identity row's rename-candidate sub-clause had zero mechanical
# backstop (existing sibling hooks only cover RAG/claudify/skip-condition
# sub-rows), so it kept getting dropped when a cleanup report was composed
# from memory of a prior pass instead of re-reading run.md's literal template.
#
# Escalation policy (cleanup/run.md): cleanup-procedure class already
# hook-active for 2 mechanisms; this is a 3rd mechanism for the same class.

if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi

HG_CLEANUP_MARKERS="${HG_CLEANUP_MARKERS:-(^|[[:space:]])/cleanup|cleanup run|cleanup wrap-up|Session Ended|Session Cleanup}"
HG_SESSION_ID_MARKERS="${HG_SESSION_ID_MARKERS:-Session ID:|session[[:space:]]+id:}"

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

# Only fire on cleanup/session-end context responses
if ! echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_MARKERS"; then
  exit 0
fi

# Only fire when the response actually emits a Session ID line (the row this
# rule enforces) — a cleanup response that never reaches Step 5 is not a
# violation of this specific row yet.
if ! echo "$RESPONSE" | grep -qiE "$HG_SESSION_ID_MARKERS"; then
  exit 0
fi

# The row is satisfied if a `/rename` command token appears anywhere in the
# response (candidates are often listed as separate code spans).
if echo "$RESPONSE" | grep -qE "/rename[[:space:]]"; then
  exit 0
fi

cat <<'EOF'
{
  "decision": "block",
  "reason": "Cleanup/session-end report includes a 'Session ID:' line but no accompanying `/rename <model>-<topic>-<sessid8>` recommendation (2-3 candidates). cleanup/run.md Step 5's 'Session identity (mandatory)' row requires both together — re-read the row's literal text (do not reconstruct it from memory of a prior pass) and add the rename candidates as standalone `/rename ...` code spans (no label/colon inside the span, so a single copy-paste is directly runnable)."
}
EOF
exit 2
