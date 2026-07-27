#!/usr/bin/env bash
# PostToolUse:Edit|Write — advise fixing OPEN fix_plan/checklist items that
# deviate from the add.md authoring schema.
#
# Schema enforced (fix-plan/add.md):
#   - Action  : the "- [ ]" / "- [BLOCKED:...]" line itself
#   - Why     : "**Why**" sub-bullet          (mandatory)
#   - How     : "**How to apply**" sub-bullet (mandatory)
#   - Budget  : item body <= 7 lines          (verbose content belongs in artifacts)
#
# Scope (deliberately disjoint from block-fixplan-completed-bloat.sh):
#   this hook  -> OPEN items only ("- [ ]", "- [BLOCKED...]", any non-[x] marker)
#   bloat hook -> COMPLETED "- [x]" items only
#   The two never fire on the same item, so no duplicate advisory.
#
# Only the EDITED TEXT is inspected (Edit.new_string / Write.content), not the
# whole file. Pre-existing items that already violate the schema stay silent —
# the advisory targets what the session just wrote.
#
# Channel: PostToolUse stderr + exit 2 is LLM-exposed. ADVISORY only — the edit
# has already been applied; exit 2 surfaces the message so the assistant can
# correct the item on the next turn. Autonomous loops write this file often, so
# this must never hard-block.

INPUT=$(cat)
BUDGET=7
MAX_REPORT=5

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

FP=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
case "$FP" in
  */fix_plan.md|*/checklist.md) ;;
  *) exit 0 ;;
esac

# Edited text only. Edit -> new_string, Write -> content, MultiEdit -> all new_strings.
NEW=$(printf '%s' "$INPUT" | jq -r '
  .tool_input.new_string //
  .tool_input.content //
  ([.tool_input.edits[]?.new_string] | join("\n")) //
  empty
' 2>/dev/null)
[ -z "$NEW" ] && exit 0

# Anchor/context text carried THROUGH the edit (Edit -> old_string, MultiEdit ->
# all old_strings; Write has none). An item header that appears here too is a
# pre-existing anchor whose body may lie OUTSIDE the edit window: inserting a new
# item BEFORE an existing one leaves that existing item's header as the trailing
# line of new_string while its Why/How stay below the cut. Flagging it would
# misfire (the exact false-positive this exemption removes). The advisory targets
# only items the session actually authored in this edit.
OLD=$(printf '%s' "$INPUT" | jq -r '
  .tool_input.old_string //
  ([.tool_input.edits[]?.old_string] | join("\n")) //
  empty
' 2>/dev/null)

# A top-level item starts at column 0 with "- [". Its span runs until the next
# top-level "- [" line, a "#"-header line, or EOF. OLD is fed before a separator
# so awk can collect anchor headers, then the NEW section is inspected.
FINDINGS=$(printf '%s\n===HOOK_OLD_NEW_SEP===\n%s' "$OLD" "$NEW" | awk -v budget="$BUDGET" -v maxrep="$MAX_REPORT" '
  BEGIN { reading_old = 1 }
  reading_old && /^===HOOK_OLD_NEW_SEP===$/ { reading_old = 0; next }
  reading_old { if ($0 ~ /^- \[/) oldhead[$0] = 1; next }
  function flush(endnr,   span, probs) {
    # Exempt completed [x] items (bloat hook owns those), [BLOCKED] items, and
    # anchor items carried from old_string (is_anchor) whose body may be cut off
    # by the edit boundary. A BLOCKED item is an external-wait entry whose schema
    # is a trigger line ("**trigger: <condition>**"), not the Action/Why/How of
    # an act-now item — the whole Hold section uses that form, so requiring
    # Why/How here misfires.
    if (!in_item || is_done || is_blocked || is_anchor) { in_item = 0; return }
    span = endnr - start + 1
    probs = ""
    if (!has_why) probs = probs "Why "
    if (!has_how) probs = probs "How-to-apply "
    if (span > budget) probs = probs "over-budget(" span " > " budget " lines) "
    if (probs != "" && n < maxrep) {
      n++
      printf "  %s\n      missing/over: %s\n", substr(head, 1, 72), probs
    }
    in_item = 0
  }
  /^- \[/ {
    flush(NR - 1)
    start = NR; head = $0; in_item = 1
    is_done = ($0 ~ /^- \[x\]/)
    is_blocked = ($0 ~ /\[BLOCKED/)
    is_anchor = ($0 in oldhead)
    has_why = 0; has_how = 0
    next
  }
  /^#/ { flush(NR - 1); next }
  in_item {
    if ($0 ~ /\*\*Why\*\*/)          has_why = 1
    if ($0 ~ /\*\*How to apply\*\*/) has_how = 1
  }
  END { flush(NR) }
')

[ -z "$FINDINGS" ] && exit 0

{
  echo "ADVISORY (fix_plan item schema): open item(s) in this edit deviate from the add.md schema:"
  echo "$FINDINGS"
  echo "Each open item needs all three elements:"
  echo "  - [ ] {Action — imperative, one sentence}"
  echo "    - **Why**: {motivation, 1-2 sentences — future sessions cannot recover this}"
  echo "    - **How to apply**: {procedure / tools / verification}"
  echo "Body budget is ${BUDGET} lines. Diagnostics, option matrices and long context go to"
  echo "research-<slug>.md / plan-<slug>.md; the item carries a one-line path reference."
  echo "Details: /fix-plan add"
} >&2
exit 2
