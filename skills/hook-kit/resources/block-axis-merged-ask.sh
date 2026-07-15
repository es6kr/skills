#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block axis-merged single-question with multiple finding types
#
# Trigger: AskUserQuestion called with questions.length == 1 AND options
#          containing 2+ distinct finding-type keywords (Refactor/Tip/Nitpick/
#          Critical/Important/Minor) or 2+ distinct file:line identifiers.
# Action: Deny with guidance to split into multiple questions in the questions array.
#
# Background: ask-user-question.md "Parallel decision tracks must split into a questions array (HARD STOP)".
# failed-attempts.md tracks 3 recurrences (2026-05-04, 2026-05-16, 2026-05-28).
# Rule strengthening alone did not prevent recurrence; this hook automates the gate.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

# Get questions count
QCOUNT=$(echo "$INPUT" | jq -r '.tool_input.questions | length' 2>/dev/null)
if [[ -z "$QCOUNT" || "$QCOUNT" != "1" ]]; then
  # 0 questions = invalid input (let other validation handle); 2+ = axis already split (OK)
  exit 0
fi

# Collect axis-detection text: question text + option labels only.
# Description body is excluded — it often lists affected files / explanations
# for a SINGLE axis decision (e.g., "adopt this rule → PROMPT.md/fix_plan.md changes").
# False-positive case (2026-05-29): single-axis ask "adopt rule?" with 3 file
# paths in descriptions → previously triggered axis-merged DENY incorrectly.
OPT_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[0] |
  (.question // ""),
  (.options[]? | .label // "")
' 2>/dev/null)

if [[ -z "$OPT_TEXT" ]]; then
  exit 0
fi

# Detect finding-type keywords (case-insensitive, word-boundary-ish)
FINDING_KEYWORDS=$(echo "$OPT_TEXT" | grep -oiE '\b(Refactor|Tip|Nitpick|Critical|Important|Minor)\b' | sort -u)
FINDING_COUNT=$(echo "$FINDING_KEYWORDS" | grep -c . 2>/dev/null || echo 0)

# Detect file:line identifiers (e.g., variables.tf:172, main.tf:14-27, inventory.yml:138)
PATH_LINE=$(echo "$OPT_TEXT" | grep -oE '[A-Za-z0-9_/.-]+\.(tf|tfvars|md|ya?ml|ts|tsx|js|jsx|py|go|rs|sh|sql|java|kt)(:[0-9]+(-[0-9]+)?)?' | sort -u)
PATH_COUNT=$(echo "$PATH_LINE" | grep -c . 2>/dev/null || echo 0)

# Trigger if either signal is 2+
if [[ "$FINDING_COUNT" -ge 2 || "$PATH_COUNT" -ge 2 ]]; then
  {
    echo "DENIED: AskUserQuestion has questions.length == 1 but options span multiple independent axes."
    echo ""
    echo "Detected axis signals:"
    if [[ "$FINDING_COUNT" -ge 2 ]]; then
      echo "  Finding-type keywords (${FINDING_COUNT} distinct):"
      echo "$FINDING_KEYWORDS" | sed 's/^/    - /'
    fi
    if [[ "$PATH_COUNT" -ge 2 ]]; then
      echo "  File/path identifiers (${PATH_COUNT} distinct):"
      echo "$PATH_LINE" | sed 's/^/    - /'
    fi
    echo ""
    echo "Why blocked:"
    echo "  - Each finding/file = independent decision axis (apply / register-separate / defer)"
    echo "  - Single question forces a single-choice selection, stripping user's per-axis decision authority"
    echo "  - failed-attempts.md 'axis-merged single-question' 3 recurrences (2026-05-04, 2026-05-16, 2026-05-28)"
    echo ""
    echo "Required: split into multiple questions in the questions array."
    echo ""
    echo "Correct pattern (example):"
    echo "  AskUserQuestion({"
    echo "    questions: ["
    echo "      { question: '[#1 Refactor variables.tf] how to handle?', options: [apply, register-separate, defer] },"
    echo "      { question: '[#2 Tip main.tf] how to handle?', options: [apply, defer] },"
    echo "      { question: '[#3 Nitpick inventory.yml] how to handle?', options: [apply, register-separate, defer] }"
    echo "    ]"
    echo "  })"
    echo ""
    echo "Reference: ask-user-question.md 'Parallel decision tracks must split into a questions array (HARD STOP)'"
  } >&2
  exit 2
fi

exit 0
