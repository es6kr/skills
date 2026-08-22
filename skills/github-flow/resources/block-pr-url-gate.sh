#!/usr/bin/env bash
# block-pr-url-gate.sh — PR/issue reference gate for decision-UI payloads.
#
# Registered under two matchers (see hooks/hooks.json):
#   - PreToolUse:AskUserQuestion — every distinct PR/issue number surfaced in
#     a question/option needs its own clickable full URL somewhere in that
#     same ask. A bare "#N" is ambiguous once the ask can span multiple repos.
#     Rule: wip/resume.md "Per-item direction ask" Don't/Do row 6.
#   - PreToolUse:TaskCreate — a PR/issue reference in a task `subject` needs
#     a repo qualifier in the subject itself (e.g. "owner/repo PR #N: ..."),
#     because TaskList never displays `description`.
#     Rule: wip/resume.md "Medium separation principle" Don't/Do row 5.
#
# Both checks share one shape: bare "#N" present, but no accompanying
# repo-qualified reference (full GitHub URL for the ask case, "owner/repo"
# token for the TaskCreate case) present in the same payload.

set -uo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "AskUserQuestion" && "$TOOL_NAME" != "TaskCreate" ]] && exit 0

BARE_REF_PATTERN='#[0-9]+'
FULL_URL_PATTERN='https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(pull|issues)/[0-9]+'
REPO_QUALIFIER_PATTERN='[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+[^/#]{0,20}#[0-9]+'

# ============================================================================
# AskUserQuestion: bare "#N" without a full clickable URL anywhere in the ask
# ============================================================================
check_ask_bare_ref() {
  local ask_text
  ask_text=$(echo "$INPUT" | jq -r '
    .tool_input.questions[]? |
    (.question // ""),
    (.options[]? | (.label // ""), (.description // ""))
  ' 2>/dev/null)

  [[ -z "$ask_text" ]] && return 0
  echo "$ask_text" | grep -qE "$BARE_REF_PATTERN" || return 0
  echo "$ask_text" | grep -qE "$FULL_URL_PATTERN" && return 0

  cat >&2 <<'MSG'
DENIED: AskUserQuestion references a PR/issue by bare "#N" without a full URL.

Why blocked:
  - The question text or an option's label/description contains "#N"
  - But no full clickable URL (https://github.com/<owner>/<repo>/pull|issues/<N>)
    appears anywhere in this same ask

Why this matters:
  - An ask can surface work spanning multiple repos. A bare "#N" is
    ambiguous the moment a second repo's PR/issue could also match that
    number — the user cannot tell which repo it refers to without opening
    a separate lookup.

Required action (pick one before retrying):
  1. Add the full URL next to the "#N" reference (e.g. "PR #184
     (https://github.com/<owner>/<repo>/pull/184)")
  2. If multiple PR/issue numbers appear, give each its own full URL
  3. Run `gh pr view <N>` / `gh issue view <N>` first to confirm the URL
     before including it — do not fabricate one

Reference: wip/resume.md "Per-item direction ask" Don't/Do row 6.
MSG
  exit 2
}

# ============================================================================
# TaskCreate: bare "#N" in `subject` without a repo qualifier in the subject
# ============================================================================
check_taskcreate_bare_ref() {
  local subject
  subject=$(echo "$INPUT" | jq -r '.tool_input.subject // empty' 2>/dev/null)

  [[ -z "$subject" ]] && return 0
  echo "$subject" | grep -qE "$BARE_REF_PATTERN" || return 0
  echo "$subject" | grep -qE "$REPO_QUALIFIER_PATTERN" && return 0

  cat >&2 <<'MSG'
DENIED: TaskCreate subject references a PR/issue by bare "#N" without a repo qualifier.

Why blocked:
  - `subject` contains "#N"
  - But no "owner/repo ... #N" style qualifier is present in the subject
    itself

Why this matters:
  - `TaskList` displays `subject` only — `description` is never shown.
    A bare "#184" in the subject is unrecoverably ambiguous the moment two
    tracked repos both have a PR/issue #184.

Required action:
  - Prefix the subject with the repo qualifier, e.g.
    "owner/repo PR #184: <short description>"
  - Put any additional detail (full URL, context) in `description` as usual

Reference: wip/resume.md "Medium separation principle" Don't/Do row 5.
MSG
  exit 2
}

case "$TOOL_NAME" in
  AskUserQuestion) check_ask_bare_ref ;;
  TaskCreate)       check_taskcreate_bare_ref ;;
esac

exit 0
