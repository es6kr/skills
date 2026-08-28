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
# Receiver binding comes from the workspace bindings config, not from a caller
# flag: when the `rag` role resolves to `kind: none` this hook stays silent, per
# that config's contract that consumers skip rather than block.
#
# Background: the caller-side dispatch rule recurred 3 times:
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

# Receiver gate: only warn when this workspace actually binds a RAG receiver.
# An unconfigured role (`kind: none`) or an unresolvable config is a valid state,
# so the hook exits quietly instead of nagging for a flag that is not required.
WSCFG_SHIM="$(dirname "$0")/workspace-config.sh"
RAG_KIND=""
if [[ -x "$WSCFG_SHIM" ]]; then
  RAG_KIND=$(bash "$WSCFG_SHIM" --export 2>/dev/null | sed -n 's/^WSCFG_RAG_KIND=//p' | head -1)
fi
[[ -z "$RAG_KIND" || "$RAG_KIND" == "none" ]] && exit 0

# Best-effort: check session transcript for prior qdrant-store invocation.
TRANSCRIPT="${CLAUDE_TRANSCRIPT_PATH:-}"
if [[ -n "$TRANSCRIPT" && -r "$TRANSCRIPT" ]]; then
  # Detect BOTH dispatch surfaces:
  #   (a) MCP tool call  — mcp__<vendor>__*-store
  #   (b) CLI dispatch   — the receiver topic's own documented script path, which is
  #       what `--rag=<skill>:<topic>` actually shells out to. Omitting (b) made this
  #       hook fire on correctly-dispatched writes (the caller stored via the script,
  #       the hook only looked for the MCP tool and saw nothing).
  if grep -qE 'mcp__[a-z_]+__[a-z-]*store|"name":[[:space:]]*"[a-z-]*store"|--rag=|qdrant-import\.py|qdrant-store-chunk\.py|qdrant-fact\.py|fix-plan-to-qdrant\.py' "$TRANSCRIPT" 2>/dev/null; then
    # Already dispatched in this session — quiet exit
    exit 0
  fi
fi

# Warn — PostToolUse surfaces the stderr message to the model only on exit 2
# (exit 1 is a non-blocking error and stays hidden).
cat >&2 <<EOF
[block-research-plan-without-rag] $FILE_PATH

RAG dispatch missing. This workspace binds a RAG receiver (WSCFG_RAG_KIND=$RAG_KIND),
so the artifact should reach it before the file is archived away.

Required action (pick one):
  1. Dispatch to the receiver resolved by workspace-config.sh (WSCFG_RAG_* values)
  2. Pass --no-rag when this artifact is deliberately not indexed

No flag is required to dispatch — the binding is resolved from the workspace config.
Storing before archiving to .bak/ is what prevents permanent data loss.
EOF
exit 2
