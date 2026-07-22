#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block TaskList internal ID exposure in question/options
#
# Trigger: AskUserQuestion question/option text containing #NN patterns
#          without an immediately adjacent PR/issue/pull/task context prefix.
# Action: Deny with guidance to use subject keyword instead.
#
# Background: TaskList internal IDs and GitHub PR/issue numbers both use #NN format,
# causing user confusion. TaskList IDs are NOT shown in the user's UI, so bare #NN
# in an option label is meaningless to the user and collides with PR/issue numbers.
# Recurrences tracked in failed-attempts.md (2026-05-13, 2026-05-16, 2026-07-06 — 3rd).
# The hook was authored after the 2nd recurrence but was lost (orphan hook, no skill
# resources/ home) → re-homed here in hook-kit/resources/ so /hook audit tracks it.
# Rule strengthening alone did not prevent recurrence; this hook automates the gate.
#
# PR-URL gate (2nd guard, same file): any PR reference in ask text requires a
# clickable PR URL somewhere in the same questions payload, so the user can open
# and inspect the PR before deciding. A bare "PR #N" — even with the repo name —
# is insufficient. Tracked in failed-attempts.md (grep "bare PR", 3rd recurrence).

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

# Collect all searchable text: question, option label, option description
TEXTS=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.question // ""),
  (.options[]? | (.label // ""), (.description // ""))
' 2>/dev/null)

VIOLATIONS=()

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  # Extract each #NN occurrence with preceding 25 chars of context
  while IFS= read -r snippet; do
    [[ -z "$snippet" ]] && continue
    # Check if PR/issue/pull/task keyword precedes the #NN in this snippet
    if echo "$snippet" | grep -qiE '(PR|issue|pull|task)[[:space:]]*#[0-9]'; then
      continue
    fi
    # Check for github.com / gitlab URL context
    if echo "$snippet" | grep -qiE 'github\.com|gitlab'; then
      continue
    fi
    VIOLATIONS+=("$snippet")
  done < <(echo "$line" | grep -oE '.{0,25}#[0-9]{1,3}([^0-9]|$)')
done <<< "$TEXTS"

# --- PR-URL gate: PR reference present but no PR URL anywhere in the payload ---
if echo "$TEXTS" | grep -qiE '\bPR[[:space:]]*#?[0-9]+'; then
  if ! echo "$TEXTS" | grep -qiE 'https://github\.com/[^[:space:])]+/pull/[0-9]+|https://[^[:space:])]*gitlab[^[:space:])]+/-/merge_requests/[0-9]+'; then
    {
      echo "DENIED: AskUserQuestion references a PR without exposing its URL."
      echo ""
      echo "Why blocked:"
      echo "  - An ask is a self-contained decision UI: the user must be able to open"
      echo "    and inspect the PR before deciding, without hunting through scroll-back"
      echo "  - A bare 'PR #N' — even with the repo name — is not clickable"
      echo ""
      echo "Required action:"
      echo "  Include the full PR URL (https://github.com/<owner>/<repo>/pull/<N>)"
      echo "  in the question text or the relevant option's description, then retry."
      echo ""
      echo "Reference: question skill options.md section 4 (metadata + full URL);"
      echo "  failed-attempts.md (grep \"bare PR\")"
    } >&2
    exit 2
  fi
fi

if [[ ${#VIOLATIONS[@]} -eq 0 ]]; then
  exit 0
fi

{
  echo "DENIED: AskUserQuestion contains TaskList ID pattern (#NN) without PR/issue context."
  echo ""
  echo "Why blocked:"
  echo "  - TaskList internal IDs are NOT shown in the user's UI; a bare #NN option label is meaningless to the user"
  echo "  - TaskList IDs and GitHub PR/issue numbers both use #NN → user cannot distinguish"
  echo "  - Previous violations recorded in failed-attempts.md (3rd recurrence)"
  echo ""
  echo "Violating snippets (with preceding context):"
  for v in "${VIOLATIONS[@]}"; do
    echo "  - $v"
  done
  echo ""
  echo "Required action (pick one before retrying):"
  echo "  1. Replace TaskList ID with subject keyword (e.g., 'dev branch feat/... promote', 'staging PR routing')"
  echo "  2. If #NN refers to GitHub PR/issue, add explicit prefix: 'PR #NN' or 'issue #NN'"
  echo ""
  echo "Reference: ~/.claude/skills/todowrite/conversation-id.md 'TaskList Conversation IDs (HARD STOP)'"
} >&2

exit 2
