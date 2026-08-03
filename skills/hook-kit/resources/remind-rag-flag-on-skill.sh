#!/usr/bin/env bash
# PreToolUse:Skill — Remind to supply --rag=<skill>:<topic> when invoking
# a generic skill that exposes a --rag dispatch contract.
#
# Generic skills supporting --rag dispatch (whitelist):
#   - cleanup:fa-prune       (Section 8)
#   - archive (any topic)    (RAG dispatch section)
#   - code-workflow (any)    (RAG dispatch contract at steps.md)
#
# Behavior:
#   - If invoking a whitelisted skill without --rag= in args → DENY with
#     reminder. Caller can re-invoke with --rag=<skill>:<topic> or include
#     'no-rag-dispatch' in args to opt out for this call.
#
# Override keyword in args body: 'no-rag-dispatch'
#
# Exit codes:
#   0 = allow
#   2 = block + stderr reminder

set -uo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "Skill" ]] && exit 0

SKILL=$(echo "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null)
ARGS=$(echo "$INPUT" | jq -r '.tool_input.args // empty' 2>/dev/null)

[[ -z "$SKILL" ]] && exit 0

# Whitelist matching
is_whitelist=0
case "$SKILL" in
  cleanup)
    if [[ "$ARGS" == fa-prune* ]]; then is_whitelist=1; fi
    ;;
  archive|code-workflow)
    is_whitelist=1
    ;;
esac

[[ "$is_whitelist" -eq 0 ]] && exit 0

# --rag= present → allow
if echo "$ARGS" | grep -qE -- '--rag=[A-Za-z0-9_-]+:[A-Za-z0-9_-]+'; then
  exit 0
fi

# Opt-out keyword in args → allow
if echo "$ARGS" | grep -q 'no-rag-dispatch'; then
  exit 0
fi

# Whitelist + no --rag + no opt-out → DENY with reminder
{
  echo "DENIED: invoking generic skill with --rag dispatch contract but no --rag flag supplied."
  echo ""
  echo "Why blocked:"
  echo "  - Skill '$SKILL' (args: '$ARGS') is in the --rag dispatch whitelist"
  echo "  - skill-usage.md 'Generic skill invocation must auto-supply available vendor dispatch' rule (caller responsibility)"
  echo "  - Missing --rag means generated artifacts (research/plan/archived sections) won't be indexed to the RAG store"
  echo ""
  echo "Required action (pick one before retrying):"
  echo "  1. Re-invoke with --rag=<receiver-skill>:<topic>"
  echo "     Example: Skill('cleanup', 'fa-prune --rag=es6kr:qdrant-import')"
  echo "     The receiver-skill is whichever RAG-store skill you have registered."
  echo "  2. If the current environment has no RAG receiver (find/store tool absent),"
  echo "     include 'no-rag-dispatch' anywhere in the args to opt out for this call."
  echo "     Example: Skill('cleanup', 'fa-prune no-rag-dispatch')"
  echo ""
  echo "Whitelist (skills with --rag dispatch contract):"
  echo "  - cleanup:fa-prune"
  echo "  - archive (any topic)"
  echo "  - code-workflow (any topic)"
} >&2
exit 2
