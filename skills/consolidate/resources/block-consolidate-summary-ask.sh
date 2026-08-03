#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block consolidate Axis A (Findings handling) ask
#
# Trigger: AskUserQuestion options containing the "Post summary + Fix + Skip" pattern
#          that signifies consolidate decide.md Step 5 Axis A (Findings handling).
# Action: Deny with guidance to auto-proceed to Step 7.
#
# Background: AI Review Summary posting is a procedure (not a user decision).
#             Findings are auto-registered as deferred at Step 7.6.
#             Code fixes happen at Step 8 next-action only on explicit user instruction.
# See: failed-attempts.md "review request bypassing user judgment with code edit"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

# Collect all option labels + descriptions
OPT_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.options[]? | (.label // ""), (.description // ""))
' 2>/dev/null)

if [[ -z "$OPT_TEXT" ]]; then
  exit 0
fi

# Detect Axis A signature: "Post summary" + "Fix actionable/items" + "Skip" all three present
HAS_POST_SUMMARY=$(echo "$OPT_TEXT" | grep -ciE 'post[[:space:]]+summary' || true)
HAS_FIX_ACTIONABLE=$(echo "$OPT_TEXT" | grep -ciE 'fix[[:space:]]+([0-9]+[[:space:]]+)?(actionable|items|findings)' || true)
HAS_SKIP=$(echo "$OPT_TEXT" | grep -ciE '(^|[[:space:]])skip([[:space:]]|$)' || true)

# All three signatures must appear to indicate consolidate Axis A
if [[ "$HAS_POST_SUMMARY" -gt 0 && "$HAS_FIX_ACTIONABLE" -gt 0 && "$HAS_SKIP" -gt 0 ]]; then
  {
    echo "DENIED: AskUserQuestion has consolidate Axis A (Findings handling) signature."
    echo "        Auto-procedure required — no user ask at this step."
    echo ""
    echo "Why blocked:"
    echo "  - Detected 'Post summary' + 'Fix actionable/items' + 'Skip' option pattern"
    echo "  - AI Review Summary posting is a procedure (not a user decision)"
    echo "  - Findings auto-register at Step 7.6 (fix_plan.md [REVIEW_FEEDBACK], defer by default)"
    echo "  - Code fix is at Step 8 next-action only on explicit user instruction"
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Proceed Step 7 automatically — Summary posts + Step 7.6 auto-deferred registration"
    echo "  2. Step 5 is Axis B (Formal Review) only — ask only when there is a requested reviewer"
    echo "  3. Code fix belongs to Step 8 next-action ask (separate step)"
    echo ""
    echo "Reference: failed-attempts.md 'review request bypassing user judgment with code edit'"
    echo "          consolidate/decide.md Step 5 'Axis A ask forbidden (HARD STOP)'"
  } >&2
  exit 2
fi

exit 0
