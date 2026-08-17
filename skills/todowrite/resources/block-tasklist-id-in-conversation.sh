#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — block bare TaskList-ID (#NN) exposure in question/options.
#
# Owning skill: todowrite (conversation-id.md "TaskList Conversation IDs" is the
# rule this hook enforces). Previously lived in hook-kit/resources/ as a
# consolidated check inside ask-guard.sh — re-homed here per automation.md's
# hook-ownership policy (a domain-specific hook belongs to its domain skill,
# not the hook-kit catch-all). See failed-attempts.md "hook ownership:
# TaskList-ID check" for the re-homing history.
#
# Background: TaskList internal IDs and GitHub PR/issue numbers both use #NN
# format. TaskList IDs are NOT shown in the user's UI, so a bare #NN in an
# option label is meaningless to the user and collides visually with PR/issue
# numbers.
#
# PR-URL gate (2nd guard, same file): every DISTINCT PR number referenced in ask
# text requires its OWN matching clickable PR URL somewhere in the same questions
# payload, so the user can open and inspect each PR before deciding. A bare "PR #N"
# — even with the repo name — is insufficient, and one PR's URL does not satisfy
# references to other PR numbers in the same payload (payload-wide "any URL exists"
# checking under-enforces multi-PR asks). Enforces question skill options.md
# section 4. Tracked in failed-attempts.md (grep "bare PR").
#
# The gate was authored in the hook-kit copy of this file, then silently dropped
# when the TaskList-ID check was re-homed here: the re-home carried only the
# TaskList-ID logic, and the split-out target the refactor announced
# (github-flow/resources/block-pr-url-gate.sh) was never created. The surviving
# hook-kit copy kept the gate but was never registered in hooks/hooks.json, so
# the gate stopped running entirely. Merged back here and the hook-kit copy
# deleted so exactly one implementation exists, on the registered path.

set -uo pipefail

if [[ "${1:-}" == "--test" ]]; then
  SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  pass=0; fail=0
  check() {  # check <DENY|ALLOW> <question_json>
    local expect="$1" payload="$2" rc got
    echo "$payload" | bash "$SELF" >/dev/null 2>&1
    rc=$?
    case "$rc" in 2) got=DENY;; *) got=ALLOW;; esac
    if [[ "$expect" == "$got" ]]; then
      pass=$((pass+1))
    else
      fail=$((fail+1)); printf 'FAIL  expected=%-5s got=%-5s :: %s\n' "$expect" "$got" "$payload"
    fi
  }

  check DENY  '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"clean up #118","description":"x"}]}]}}'
  check DENY  '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"cleanup #328, #329","description":"x"}]}]}}'
  # Known edge case (inherited from the original pattern, not fixed here — out
  # of scope for this re-homing): "Task #N" matches the ordinal-reference
  # exception (meant for "consolidate review Task #3" style enumeration), so a
  # literal "task #118" bare TaskList reference is NOT denied. See
  # failed-attempts.md "TaskList-ID hook: Task-word ordinal-exception ambiguity".
  check ALLOW '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"do task #118","description":"x"}]}]}}'
  # PR-URL gate: a PR reference needs its OWN clickable URL in the same payload
  check DENY  '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"merge PR #118","description":"x"}]}]}}'
  check ALLOW '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"merge PR #118","description":"https://github.com/es6kr/skills/pull/118"}]}]}}'
  # one PR URL does not cover a different PR number in the same payload
  check DENY  '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"PR #12 https://github.com/es6kr/claude-plugins/pull/12","options":[{"label":"also PR #13","description":"x"}]}]}}'
  check ALLOW '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"PR #12 https://github.com/es6kr/claude-plugins/pull/12","options":[{"label":"also PR #13","description":"https://github.com/es6kr/claude-plugins/pull/13"}]}]}}'
  check ALLOW '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"see issue #42","description":"x"}]}]}}'
  check ALLOW '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"Finding #3 is real","description":"x"}]}]}}'
  check ALLOW '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"already merged #57","description":"x"}]}]}}'
  check ALLOW '{"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"q","options":[{"label":"see https://github.com/es6kr/skills/pull/60","description":"x"}]}]}}'
  check ALLOW '{"tool_name":"Bash","tool_input":{"command":"echo #123 not an ask"}}'

  echo "Total: $((pass+fail)), Pass: $pass, Fail: $fail"
  [[ "$fail" -eq 0 ]] && exit 0 || exit 1
fi

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

ASK_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.question // ""),
  (.options[]? | (.label // ""), (.description // ""))
' 2>/dev/null)

# --- PR-URL gate: each DISTINCT PR number must have its own matching URL ---
# (payload-wide "any URL exists" checking under-enforces multi-PR asks — a URL
# for PR #A does not satisfy a bare reference to PR #B in the same payload)
PR_NUMS_REFERENCED=$(echo "$ASK_TEXT" | grep -oiE '\bPR[[:space:]]*#?[0-9]+' | grep -oE '[0-9]+' | sort -un)
if [[ -n "$PR_NUMS_REFERENCED" ]]; then
  PR_NUMS_WITH_URL=$(echo "$ASK_TEXT" | grep -oiE 'https?://[^[:space:])]+/(pull|merge_requests)/[0-9]+' | grep -oE '[0-9]+$' | sort -un)
  MISSING_URL_FOR=()
  while IFS= read -r n; do
    [[ -z "$n" ]] && continue
    if ! grep -qxF "$n" <<< "$PR_NUMS_WITH_URL"; then
      MISSING_URL_FOR+=("$n")
    fi
  done <<< "$PR_NUMS_REFERENCED"
  if [[ ${#MISSING_URL_FOR[@]} -gt 0 ]]; then
    {
      echo "DENIED: AskUserQuestion references PR number(s) without a matching URL for each."
      echo ""
      echo "Why blocked:"
      echo "  - An ask is a self-contained decision UI: the user must be able to open"
      echo "    and inspect EVERY referenced PR before deciding, without hunting through"
      echo "    scroll-back"
      echo "  - A bare 'PR #N' — even with the repo/project name — is not clickable"
      echo "  - One PR's URL does not satisfy references to a DIFFERENT PR number in the"
      echo "    same payload — each distinct number needs its own URL"
      echo ""
      echo "PR number(s) missing their own URL: ${MISSING_URL_FOR[*]}"
      echo ""
      echo "Required action:"
      echo "  Add the full PR/MR URL (e.g., https://github.com/<owner>/<repo>/pull/<N> or"
      echo "  GitLab MR URL) for each PR number listed above, in the question text or"
      echo "  the relevant option's description, then retry."
      echo ""
      echo "Reference: question skill options.md section 4 (metadata + full URL);"
      echo "  failed-attempts.md (grep \"bare PR\")"
    } >&2
    exit 2
  fi
fi

# PR / issue / pull #N -> explicit GitHub reference, allowed
ISSUE_PREFIX='(PR|issue|pull)[[:space:]]*#[0-9]|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]'
# Explicit enumeration prefix -> not a TaskList ID, an ordinal reference
# (e.g., "Finding #3", "Item #5", "Section #N", "Important #1", "Nitpick #2",
#  "Critical #4", "Comment #1", "Walkthrough #2", "Task #3")
FINDING_PREFIX='(Finding|Item|Section|Important|Nitpick|Critical|Comment|Walkthrough|Task)[[:space:]]*#[0-9]'
# Past-tense merge / history reference -> not an active task
RETROSPECT_PR='(merged|MERGED|previously|prior)[^0-9]{0,20}#[0-9]'

VIOLATIONS=()

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  while IFS= read -r snippet; do
    [[ -z "$snippet" ]] && continue
    if echo "$snippet" | grep -qiE "$ISSUE_PREFIX"; then
      continue
    fi
    if echo "$snippet" | grep -q 'github\.com'; then
      continue
    fi
    if echo "$snippet" | grep -qiE "$FINDING_PREFIX"; then
      continue
    fi
    if echo "$snippet" | grep -qiE "$RETROSPECT_PR"; then
      continue
    fi
    VIOLATIONS+=("$snippet")
  done < <(echo "$line" | grep -oE '.{0,25}#[0-9]{1,3}([^0-9]|$)')
done <<< "$ASK_TEXT"

if [[ ${#VIOLATIONS[@]} -eq 0 ]]; then
  exit 0
fi

{
  echo "DENIED: AskUserQuestion contains TaskList ID pattern (#NN) without PR/issue context."
  echo ""
  echo "Why blocked:"
  echo "  - TaskList internal IDs are NOT shown in the user's UI; a bare #NN option label is meaningless to the user"
  echo "  - TaskList IDs and GitHub PR/issue numbers both use #NN -> user cannot distinguish"
  echo ""
  echo "Violating snippets (with preceding context):"
  for v in "${VIOLATIONS[@]}"; do
    echo "  - $v"
  done
  echo ""
  echo "Required action (pick one before retrying):"
  echo "  1. Replace TaskList ID with subject keyword (e.g., 'core clearStale task', 'Ralph improve task')"
  echo "  2. If #NN refers to a GitHub PR/issue, add an explicit prefix: 'PR #NN' or 'issue #NN'"
  echo ""
  echo "Reference: todowrite/conversation-id.md 'TaskList Conversation IDs (HARD STOP)'"
} >&2

exit 2
