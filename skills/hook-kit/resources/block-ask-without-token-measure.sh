#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Validate Context Usage Header & Physical Measurement Requirement
#
# Trigger: AskUserQuestion tool call in Antigravity/Gemini environment
# Action: Validate that Context Usage header exists and contains percentage/token estimate.
#

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" && "$TOOL_NAME" != "default_api:ask_question" && "$TOOL_NAME" != "default_api:ask_user_question" ]]; then
  exit 0
fi

# Extract question text from first question item
QUESTION_TEXT=$(echo "$INPUT" | jq -r '.tool_input.questions[0].question // .tool_input.question // empty' 2>/dev/null)

# Verify Context Usage header is present
if [[ ! "$QUESTION_TEXT" =~ Context\ Usage:.*% ]]; then
  {
    echo "DENIED: AskUserQuestion question text MUST start with [Context Usage: XX% (~YYK tokens...)] header (HARD STOP)."
    echo ""
    echo "Why blocked:"
    echo "  - Omitting physically measured context usage % violates Antigravity Next Action Suggestion Policy."
    echo "  - Physical token measurement from transcript log file bytes is mandatory before invoking AskUserQuestion."
    echo ""
    echo "Current Question Text: $QUESTION_TEXT"
    echo ""
    echo "Required Action:"
    echo "  1. Measure transcript file size (e.g. ls -l <log-dir>/transcript_full.jsonl or transcript.jsonl)."
    echo "  2. Compute tokens: tokens = transcript_full_bytes / 3.5 (1M capacity)."
    echo "  3. Format question header: [Context Usage: Physical XX.X% (~YYYK tokens based on transcript_full.jsonl)]"
    echo ""
    echo "Reference: GEMINI.md Antigravity Environment Detection & Context Usage Gate"
  } >&2
  exit 2
fi

exit 0
