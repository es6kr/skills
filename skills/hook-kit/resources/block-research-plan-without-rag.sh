#!/usr/bin/env bash
# PostToolUse:Write/Edit — Warn when research-*.md / plan-*.md is written
# without a parallel RAG dispatch (qdrant-store call or --rag= flag).
#
# Trigger: Write or Edit on a path matching:
#   - .ralph/docs/generated/research-*.md
#   - .ralph/docs/generated/plan-*.md
#   - .omc/plans/*.md (plan or research patterns)
# Action: Inject a stderr reminder to dispatch the artifact via RAG receiver.
#
# Background: skill-usage.md "Generic skill invocation must auto-supply available
# vendor dispatch" (HARD STOP) recurred 3 times:
#   1. /session archive — qdrant receiver available, --rag not supplied
#   2. /session archive — MCP-only detection, missed network receiver
#   3. /code-workflow — research/plan written, no qdrant-store call, archived
# Per fix.md "3rd recurrence = hook required (HARD STOP — implement NOW)".
#
# Detection logic:
#   - File path matches research-*.md / plan-*.md pattern above
#   - No qdrant-store call in this session transcript (best-effort heuristic
#     via $CLAUDE_TRANSCRIPT_PATH if available)
#   - If transcript is unavailable, warn unconditionally (safer to over-warn)

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Pattern match: research-*.md, plan-*.md inside generated/ or plans/
case "$FILE_PATH" in
  */.ralph/docs/generated/research-*.md) ;;
  */.ralph/docs/generated/plan-*.md) ;;
  */.omc/plans/research-*.md) ;;
  */.omc/plans/plan-*.md) ;;
  *) exit 0 ;;
esac

# Skip if path looks like an archive/.bak — those are intentional cleanups
case "$FILE_PATH" in
  *.bak/*|*/.bak/*|*~|*.archived) exit 0 ;;
esac

# Best-effort: check session transcript for prior qdrant-store invocation.
TRANSCRIPT="${CLAUDE_TRANSCRIPT_PATH:-}"
if [[ -n "$TRANSCRIPT" && -r "$TRANSCRIPT" ]]; then
  if grep -qE 'mcp__qdrant__qdrant-store|"name":[[:space:]]*"qdrant-store"|--rag=' "$TRANSCRIPT" 2>/dev/null; then
    # Already dispatched in this session — quiet exit
    exit 0
  fi
fi

# Warn — PostToolUse surfaces the stderr message to the model only on exit 2
# (exit 1 is a non-blocking error and stays hidden).
cat >&2 <<EOF
[block-research-plan-without-rag] $FILE_PATH

RAG dispatch missing. skill-usage.md "Generic skill invocation must auto-supply
available vendor dispatch" rule applies (caller responsibility).

Required action (pick one):
  1. Call mcp__qdrant__qdrant-store to store body + metadata
  2. When invoking code-workflow/fix, explicitly supply --rag=<skill>:<topic> flag
  3. Skipping is only allowed when receiver candidates = 0 (MCP unavailable + skill registry
     receiver topics = 0) — silent skip is forbidden otherwise

RAG store is mandatory before archiving to .bak/ (prevents permanent data loss).
EOF
exit 2
