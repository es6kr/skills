#!/usr/bin/env bash
# PostToolUse:Edit|Write — advise condensing an oversized completed "- [x]" item in fix_plan.md.
#
# Rationale (3-layer work-record separation):
#   tracking  = fix_plan.md  -> current state only
#   record    = RAG store    -> immutable finished-work history
#   knowledge = skills       -> durable domain facts
# A finished task's full multi-session execution log (OCIDs, IPs, phase-by-phase notes,
# incident post-mortems) is record/knowledge, not tracking. Sessions tend to *append* new
# phase blocks to an already-[x] item instead of condensing it, so a completed item bloats
# over time. This hook fires when a completed "- [x]" top-level item exceeds THRESHOLD lines,
# prompting: RAG-store the detail, move lessons to skills, then condense to a 1-line summary
# + pointers.
#
# Channel: PostToolUse stderr + exit 2 is LLM-exposed. This is ADVISORY only — the edit has
# already been applied; exit 2 surfaces the message so the assistant can condense next.
#
# Scope note: only fires for Edit/Write tool edits of fix_plan.md. Non-[x] items
# ([ ], [BLOCKED], [MERGED], [PHASE...]) are exempt — this targets completed [x] only.

INPUT=$(cat)
THRESHOLD=10

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

FP=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
case "$FP" in
  *fix_plan.md) ;;
  *) exit 0 ;;
esac
[ -f "$FP" ] || exit 0

# Report completed "- [x]" top-level items whose inline span exceeds THRESHOLD lines.
# A top-level item starts at column 0 with "- [". Its span runs until the next top-level
# "- [" line or a "#"-header line (whichever comes first) or EOF.
OVERSIZED=$(awk -v th="$THRESHOLD" '
  function flush(endnr) {
    if (in_item && is_done && (endnr - start + 1) > th) {
      printf "  L%d (~%d lines): %s\n", start, endnr - start + 1, substr(head, 1, 70)
    }
  }
  /^- \[/ {
    flush(NR - 1)
    start = NR; head = $0; in_item = 1
    is_done = ($0 ~ /^- \[x\]/) ? 1 : 0
    next
  }
  /^#/ { flush(NR - 1); in_item = 0; next }
  END { flush(NR) }
' "$FP")

[ -z "$OVERSIZED" ] && exit 0

{
  echo "ADVISORY (fix_plan bloat): completed [x] item(s) carry an oversized inline log (> ${THRESHOLD} lines):"
  echo "$OVERSIZED"
  echo ""
  echo "A tracking file holds current state, not a finished task's full multi-session log."
  echo "Per 3-layer separation (tracking / record / knowledge):"
  echo "  1. RAG-store the full detail (record layer) before removing it."
  echo "  2. Move any domain lessons to the relevant skill (knowledge layer) if not already there."
  echo "  3. Condense the [x] item to a 1-line summary + pointers (artifact file / RAG collection / skill)."
  echo "Open items ([ ], [BLOCKED], [MERGED], [PHASE...]) are exempt — this targets completed [x] only."
} >&2
exit 2
