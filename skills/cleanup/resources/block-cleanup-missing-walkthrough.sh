#!/usr/bin/env bash
# Stop event — Detect a cleanup/session-end completion report that never
# wrote a walkthrough artifact this session.
#
# Trigger: assistant response contains cleanup-completion or session-end
#          markers (same marker set as block-cleanup-missing-rename.sh)
# Detection: no Write/Edit tool_use anywhere in the transcript targeting a
#            path whose basename contains "walkthrough" (case-insensitive).
# Action: emit reminder via stdout (non-blocking read, but exit 2 blocks
#         Stop and injects context for the next turn).
#
# Background: failed-attempts.md "cleanup-report-omitted-walkthrough-artifact"
# class, 3rd recurrence — 1st/2nd occurrences (full "no walkthrough at all"
# and "walkthrough written but reported as an unclickable file:// link")
# already reached status=hook-pending, but no hook existed yet. 3rd occurrence
# was a scope error: a user's "keep it brief / --auto" instruction to shrink
# an INCREMENTAL cleanup pass was read as exempting the walkthrough artifact
# entirely, not just its length. This hook makes "was a walkthrough written
# at all this session" mechanically checkable regardless of report brevity.
#
# Deliberately NOT checking artifact CONTENT or a specific naming convention
# (workspaces vary: Antigravity brain/<id>/walkthrough.md,
# .agents/docs/generated/walkthrough-*.md, etc.) — only that *some*
# Write/Edit this session targeted a path whose basename contains
# "walkthrough". A companion hook (block-cleanup-missing-rename.sh) already
# covers the separate "was it linked plainly" failure mode.

if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi

HG_CLEANUP_MARKERS="${HG_CLEANUP_MARKERS:+${HG_CLEANUP_MARKERS}|}(^|[[:space:]])/cleanup|cleanup run|cleanup wrap-up|cleanup complete|cleanup pass|cleanup finished|Session Ended|Session Cleanup|session-end report"
HG_COMPLETION_WORDS="${HG_COMPLETION_WORDS:+${HG_COMPLETION_WORDS}|}complete|completed|finished|Session Ended|wrap-up"

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

# Only fire on cleanup/session-end context responses — same gate as the
# sibling rename hook, including brief/incremental passes (a short report
# is still a cleanup-completion report).
if ! echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_MARKERS"; then
  exit 0
fi

if [[ -z "$TRANSCRIPT_PATH" ]] || [[ ! -f "$TRANSCRIPT_PATH" ]]; then
  exit 0
fi

# Was there a walkthrough-artifact write anywhere in this session's
# transcript? Match Write/Edit tool_use blocks whose file_path basename
# contains "walkthrough" (case-insensitive). A plain grep on the raw JSONL
# is enough — file_path is always inline JSON, never wrapped.
if grep -qiE '"(file_path|filePath)"[[:space:]]*:[[:space:]]*"[^"]*walkthrough[^"]*"' "$TRANSCRIPT_PATH" 2>/dev/null; then
  exit 0
fi

cat <<'EOF'
{
  "decision": "block",
  "reason": "Cleanup/session-end completion report detected, but no Write/Edit targeting a walkthrough-named file was found anywhere in this session's transcript. A 'keep it brief' / '--auto' / incremental-only instruction shrinks the walkthrough's LENGTH, not whether it gets written at all -- see failed-attempts.md 'cleanup-report-omitted-walkthrough-artifact' 3rd occurrence. Write a walkthrough artifact (even a short one covering just this session's increment) before finishing the cleanup report, in this workspace's actual convention (e.g. .agents/docs/generated/walkthrough-*.md, or Antigravity's brain/<conversation-id>/walkthrough.md) -- and report its path as a plain, copyable absolute path (not only a markdown link), per the sibling FA class 'artifact-path-reported-as-unclickable-file-uri'."
}
EOF
exit 2
