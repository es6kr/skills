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
# WHICH items are inspected comes from the EDITED TEXT (Edit.new_string /
# Write.content): pre-existing items the session did not touch stay silent.
# WHETHER an item satisfies the schema is judged against the FILE ON DISK. This
# hook is PostToolUse, so the edit is already applied and the file holds the
# item's full body — including the sub-bullets that fall outside a narrow edit
# window. Judging from the edit window alone reports Why/How as missing whenever
# the session edits only an item's header line, which is the common case when
# rewording or re-prioritising an existing item. The file is consulted only for
# headers the edit itself introduced, so the targeting is unchanged.
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
# pre-existing anchor the session merely wrote around, not an item it authored.
OLD=$(printf '%s' "$INPUT" | jq -r '
  .tool_input.old_string //
  ([.tool_input.edits[]?.old_string] | join("\n")) //
  empty
' 2>/dev/null)

# Pass 1 — which item headers did this edit introduce? Top-level "- [" lines in
# the edited text, minus completed items (the bloat hook owns those), minus
# BLOCKED items (their schema is a "**trigger: ...**" line, not Action/Why/How),
# minus anchors carried over from old_string.
CANDIDATES=$(printf '%s\n===HOOK_OLD_NEW_SEP===\n%s' "$OLD" "$NEW" | awk '
  BEGIN { reading_old = 1 }
  reading_old && /^===HOOK_OLD_NEW_SEP===$/ { reading_old = 0; next }
  reading_old { if ($0 ~ /^- \[/) oldhead[$0] = 1; next }
  /^- \[/ {
    if ($0 ~ /^- \[x\]/) next
    if ($0 ~ /\[BLOCKED/) next
    if ($0 in oldhead) next
    if (!($0 in seen)) { seen[$0] = 1; print }
  }
')
[ -z "$CANDIDATES" ] && exit 0

FILE_TEXT=""
[ -r "$FP" ] && FILE_TEXT=$(cat "$FP")

# Pass 2 — judge each candidate. The file section is authoritative; the edited
# text is the fallback for a header the file no longer holds (unreadable path, or
# a later write moved it), which keeps the pre-file behaviour as the floor.
#
# An item's span runs from its header to its last non-blank line: the blank line
# separating two items is layout, not body, and counting it would push a
# budget-sized item over the limit purely because the file has a neighbour.
FINDINGS=$(printf '%s\n===HOOK_SEC_FILE===\n%s\n===HOOK_SEC_NEW===\n%s' \
  "$CANDIDATES" "$FILE_TEXT" "$NEW" | awk -v budget="$BUDGET" -v maxrep="$MAX_REPORT" '
  function flush(   span) {
    if (!in_item) return
    span = last_nonblank - start + 1
    if (span < 1) span = 1
    if (head in candseen) {
      if (scope == "f") {
        f_seen[head] = 1; f_why[head] = has_why; f_how[head] = has_how; f_span[head] = span
      } else {
        n_seen[head] = 1; n_why[head] = has_why; n_how[head] = has_how; n_span[head] = span
      }
    }
    in_item = 0
  }
  BEGIN { sec = 1 }
  sec == 1 && /^===HOOK_SEC_FILE===$/ { sec = 2; scope = "f"; next }
  sec == 2 && /^===HOOK_SEC_NEW===$/  { flush(); sec = 3; scope = "n"; next }
  sec == 1 {
    if ($0 ~ /^- \[/ && !($0 in candseen)) { candseen[$0] = 1; ncand++; cand[ncand] = $0 }
    next
  }
  /^- \[/ {
    flush()
    start = NR; head = $0; in_item = 1; last_nonblank = NR
    has_why = 0; has_how = 0
    next
  }
  /^#/ { flush(); next }
  in_item {
    if ($0 ~ /\*\*Why\*\*/)          has_why = 1
    if ($0 ~ /\*\*How to apply\*\*/) has_how = 1
    if ($0 ~ /[^ \t]/)               last_nonblank = NR
  }
  END {
    flush()
    for (i = 1; i <= ncand; i++) {
      h = cand[i]
      if (h in f_seen)      { why = f_why[h]; how = f_how[h]; sp = f_span[h] }
      else if (h in n_seen) { why = n_why[h]; how = n_how[h]; sp = n_span[h] }
      else continue
      probs = ""
      if (!why) probs = probs "Why "
      if (!how) probs = probs "How-to-apply "
      if (sp > budget) probs = probs "over-budget(" sp " > " budget " lines) "
      if (probs != "" && reported < maxrep) {
        reported++
        printf "  %s\n      missing/over: %s\n", substr(h, 1, 72), probs
      }
    }
  }
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
