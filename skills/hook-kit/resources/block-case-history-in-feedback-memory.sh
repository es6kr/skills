#!/usr/bin/env bash
# PreToolUse:Edit + PreToolUse:Write — block case-history content in project
# feedback memory files (memory/feedback_*.md, memory/verify-*.md).
#
# Case history (violation cases, incident dates, recurrence counts) has a
# single canonical medium: the failed-attempts store
# (~/.claude/skills/cleanup/data/failed-attempts.md). Feedback memories keep
# ONLY pure how-to-work guidance — the moment a date / violation quote /
# recurrence count appears, the content is case history and must route to
# failed-attempts.md instead. Dual-recording inflates the always-on MEMORY.md
# index and duplicates the FA medium (see failed-attempts.md, keyword
# "media separation" / "byte-trim").
#
# Detection:
#   - target file: */projects/*/memory/feedback_*.md or verify-*.md
#   - new content contains a YYYY-MM-DD date stamp, OR a case-history keyword
#     (Korean variants loaded from data/hangul-patterns.regex — git-ignored;
#     English-only fallback keeps the guard functional without locale data).

set -uo pipefail

HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_FEEDBACK_CASE_KEYWORDS="${HG_FEEDBACK_CASE_KEYWORDS:-recurrence|violation case|Nth (time|occurrence)|incident quote}"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Edit|Write) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Normalize Windows backslashes so the glob match works on both path forms.
FP="${FILE_PATH//\\//}"
case "$FP" in
  */projects/*/memory/feedback_*.md) ;;
  */projects/*/memory/verify-*.md) ;;
  *) exit 0 ;;
esac

NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty' 2>/dev/null)
[[ -z "$NEW_CONTENT" ]] && exit 0

REASON=""
if echo "$NEW_CONTENT" | grep -qE '[0-9]{4}-[0-9]{2}-[0-9]{2}'; then
  REASON="date stamp (YYYY-MM-DD)"
elif echo "$NEW_CONTENT" | grep -qE "$HG_FEEDBACK_CASE_KEYWORDS"; then
  REASON="case-history keyword"
fi
[[ -z "$REASON" ]] && exit 0

cat >&2 <<'EOF'
BLOCKED: case-history content in a feedback memory file.
Feedback memories hold ONLY pure how-to-work guidance. Violation cases,
incident dates, and recurrence counts belong in the failed-attempts store:
  ~/.claude/skills/cleanup/data/failed-attempts.md (record via /cleanup retrospect)
Strip the date/incident detail from this memory (keep only the behavioral
rule) and record the case body in failed-attempts.md instead.
EOF
echo "Matched: $REASON" >&2
exit 2
