#!/usr/bin/env bash
# Stop event — Detect cleanup wrap-up / session-end report missing RAG visibility row
#
# Trigger: assistant response contains cleanup-completion or session-end markers
# Detection: response text matches cleanup keywords + missing distinct RAG visibility row ("RAG store N chunks" or "N chunks added")
# Action: emit reminder via stdout (non-blocking, exit 0) — Stop hook cannot deny but can inject
#         context for the next user prompt to re-surface the issue
#
# Background: failed-attempts.md — RAG report visibility missing 3 recurrences:
#   1st (2026-05-27): cleanup procedure compressed — 3-C.1 qdrant import deferred to ask
#   2nd (2026-06-15): cleanup wrap-up table missing RAG row
#   3rd (2026-06-16): session-end report had RAG row buried in prose (this hook trigger)
#
# Escalation policy (cleanup/run.md): 3rd recurrence+ Stop hook automation required.

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public repo never sees Korean characters. When absent, cleanup detection
# falls back to English-only markers.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_CLEANUP_MARKERS="${HG_CLEANUP_MARKERS:-cleanup run|/cleanup|Session end|session end|End session}"
HG_CLEANUP_RAG_VISIBILITY="${HG_CLEANUP_RAG_VISIBILITY:-chunks added|qdrant}"

INPUT=$(cat)

# Extract assistant message text from Stop event payload
RESPONSE=$(echo "$INPUT" | jq -r '
  .response // .transcript // .assistant_message // empty
' 2>/dev/null)

# Fallback: try parsing transcript-based payload (varies by Stop hook implementation)
if [[ -z "$RESPONSE" ]]; then
  TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
  if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
    # Read last assistant turn from transcript
    RESPONSE=$(tail -50 "$TRANSCRIPT_PATH" | jq -r 'select(.type=="assistant") | .message.content[]?.text? // empty' 2>/dev/null | tail -100)
  fi
fi

if [[ -z "$RESPONSE" ]]; then
  exit 0
fi

# Detect cleanup-completion or session-end markers (locale variants from data/)
if ! echo "$RESPONSE" | grep -qE "$HG_CLEANUP_MARKERS"; then
  exit 0
fi

# Detect distinct RAG visibility row (must appear as a TABLE ROW or BOLD line,
# not buried in prose). Heuristics:
#   1. Markdown table row containing "RAG" + ("chunks" or locale variant)
#   2. Bold line "**chunks added**" / "**qdrant**" / locale variant
#   3. Header-like "### RAG" / "## RAG"
HAS_RAG_ROW=0
if echo "$RESPONSE" | grep -qE '^\s*\|\s*\*{0,2}[^|]*(RAG|qdrant|3-C\.1)[^|]*\*{0,2}\s*\|.*(RAG|qdrant|chunks)'; then
  HAS_RAG_ROW=1
elif echo "$RESPONSE" | grep -qE "\*\*.*($HG_CLEANUP_RAG_VISIBILITY).*\*\*"; then
  HAS_RAG_ROW=1
elif echo "$RESPONSE" | grep -qE '^#{2,3}\s+.*(RAG|qdrant)'; then
  HAS_RAG_ROW=1
fi

if [[ "$HAS_RAG_ROW" -eq 1 ]]; then
  exit 0
fi

# Detect that RAG store actually happened in this session (presence of qdrant-import / qdrant-store tool use)
# If RAG was never invoked, the missing row is expected — exit silently.
HAS_RAG_CALL=0
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  if grep -qE 'qdrant-import|qdrant-store|qdrant_store' "$TRANSCRIPT_PATH" 2>/dev/null; then
    HAS_RAG_CALL=1
  fi
fi

if [[ "$HAS_RAG_CALL" -eq 0 ]]; then
  exit 0
fi

# RAG was invoked + cleanup/session-end marker present + no visibility row
# → emit reminder. Stop hook accepts JSON output with `additionalContext` to inject.
cat <<'EOF'
{
  "decision": "block",
  "reason": "Cleanup/session-end report detected but RAG store result is not highlighted as a separate row/bold/header. failed-attempts.md \"cleanup report RAG visibility missing\" 3rd-recurrence escalation hook triggered. The next response MUST include the RAG store result in one of these formats: (a) separate markdown table row: `| **3-C.1 RAG store** | **N chunks added (receiver: <vendor>)** |` OR (b) bold line: `**RAG store summary: N chunks added (receiver: <vendor>) — session UUID <uuid>**` OR (c) separate header section `### RAG store`. Burying it as one line inside a prose list is forbidden."
}
EOF
exit 2
