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

# Ralph autonomous loop (RALPH_LOOP=1) manages RAG persistence via its own wrapper
# and has no interactive user to act on an injected reminder. Emitting the missing-RAG
# reminder every turn only adds noise the headless agent may fixate on, so pass silently.
if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public repo never sees Korean characters. When absent, cleanup detection
# falls back to English-only markers.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
# Strict cleanup-invocation markers only. Generic phrases like "End session" /
# "session end" appear in option descriptions and prose unrelated to cleanup,
# producing false positives. Use cleanup-specific phrases:
#   - `/cleanup` (slash-command invocation)
#   - `cleanup run` (skill ARGUMENTS)
#   - `cleanup wrap-up` (run.md mandated wrap-up phrase)
#   - header-form session-end report marker
# Locale-specific marker variants (the wrap-up phrase and header marker in
# non-English locales) live in data/hangul-patterns.regex (HG_CLEANUP_MARKERS).
HG_CLEANUP_MARKERS="${HG_CLEANUP_MARKERS:-/cleanup|cleanup run|cleanup wrap-up}"
HG_CLEANUP_RAG_VISIBILITY="${HG_CLEANUP_RAG_VISIBILITY:-chunks added|qdrant}"

INPUT=$(cat)

# Always extract TRANSCRIPT_PATH (needed for RAG-call detection later — not only
# for RESPONSE fallback). Earlier version scoped this inside `if [[ -z "$RESPONSE" ]]`
# which left TRANSCRIPT_PATH empty on the common path → HAS_RAG_CALL silently stayed 0.
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Extract assistant message text from Stop event payload
RESPONSE=$(echo "$INPUT" | jq -r '
  .response // .transcript // .assistant_message // empty
' 2>/dev/null)

# Fallback: try parsing transcript-based payload (varies by Stop hook implementation)
if [[ -z "$RESPONSE" ]] && [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  # Read last assistant turn from transcript
  RESPONSE=$(tail -50 "$TRANSCRIPT_PATH" | jq -r 'select(.type=="assistant") | .message.content[]?.text? // empty' 2>/dev/null | tail -100)
fi

if [[ -z "$RESPONSE" ]]; then
  exit 0
fi

# Detect cleanup-completion or session-end markers (locale variants from data/)
if ! echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_MARKERS"; then
  exit 0
fi

# Detect distinct RAG visibility row (must appear as a TABLE ROW or BOLD line,
# not buried in prose). Heuristics:
#   1. Markdown table row whose LABEL CELL (first cell after the leading |) is
#      RAG-related — not just any cell in the row. A row labeled "BLOCKED" or
#      "Commits" that happens to mention "qdrant"/"chunks" as a supporting
#      detail must NOT satisfy this check (4th recurrence — a BLOCKED row
#      containing a "qdrant readyz 200 ... N chunks" prose justification
#      passed the old any-cell regex and buried the real count).
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

# Detect that RAG store actually happened in this session.
# Match must be a tool_use entry (actual call), not prose mention/quoted skill body.
# Without parsing entry types, plain `grep qdrant-import` matches assistant text
# that merely cites the skill (e.g., quoting cleanup/run.md inline) — false positive.
HAS_RAG_CALL=0
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  # Parse jsonl: select assistant tool_use entries → inspect Bash command + MCP tool name.
  # Falls back silently if jq fails (HAS_RAG_CALL stays 0 = hook exits OK = no false block).
  if jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | (.name + " " + (.input.command? // ""))' "$TRANSCRIPT_PATH" 2>/dev/null \
       | grep -qE 'qdrant-import\.py|mcp__qdrant__|qdrant-store|qdrant_store' 2>/dev/null; then
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
