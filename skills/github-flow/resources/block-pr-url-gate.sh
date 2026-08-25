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

# Invocation log (added 2026-08-24, 4th recurrence of class=ask-option-pr-ref-missing-url):
# isolated reproduction of this hook against the exact payload from a live
# "user rejected the tool call" failure reliably blocks (exit 2), yet the live
# call produced no DENIED message on 3 consecutive prior occurrences — no
# evidence exists proving whether this hook even ran during those calls. This
# unconditional, exit-independent log line closes that evidence gap: the next
# recurrence can grep this file to prove/disprove "the hook fired at all".
DEBUG_LOG="$(dirname "$0")/block-pr-url-gate.debug.log"
{
  printf '%s\tinvoked\ttool=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(echo "$INPUT" | jq -r '.tool_name // "?"' 2>/dev/null)"
  if [[ "$(wc -l < "$DEBUG_LOG" 2>/dev/null || echo 0)" -gt 300 ]]; then
    tail -n 150 "$DEBUG_LOG" > "$DEBUG_LOG.tmp" 2>/dev/null && mv "$DEBUG_LOG.tmp" "$DEBUG_LOG" 2>/dev/null
  fi
} >> "$DEBUG_LOG" 2>/dev/null || true

# Verdict trap — fires on every exit path (early exit 0 for non-matching tool,
# any exit 2 DENIED, and the final fallthrough exit 0), so the log always
# proves whether this process reached its end and what it decided.
_bpg_verdict_log() {
  local ec=$?
  { printf '%s\texit\tcode=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$ec" >> "$DEBUG_LOG"; } 2>/dev/null || true
}
trap _bpg_verdict_log EXIT

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "AskUserQuestion" && "$TOOL_NAME" != "TaskCreate" ]] && exit 0

BARE_REF_PATTERN='#[0-9]+'
FULL_URL_PATTERN='https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(pull|issues)/[0-9]+'
REPO_QUALIFIER_PATTERN='[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+[^/#]{0,20}#[0-9]+'
ANY_URL_PATTERN='https?://[^[:space:]]+'

# Tracker-item references are NOT "#N"-shaped. A backlog tracker keyed as
# "<PROJECT>-<N>" (Plane and most Jira-likes) carries no "#", so the bare-ref
# check above cannot see it at all — the reference sails through even though it
# is exactly as ambiguous to the reader as a bare "#N".
#
# The project keys are workspace data, not gate policy, so they are read from
# the works-config file rather than hardcoded here: every profile's
# `roles.backlog.project_keys` is unioned, so an ask spanning two workspaces is
# covered by one pattern. A missing/unreadable config disables only this check
# (the "#N" checks stay live) — a config problem must never block every ask.
CONFIG_FILE="${WSCFG_CONFIG_FILE:-$HOME/.agents/config.json}"

tracker_key_alternation() {
  [[ -r "$CONFIG_FILE" ]] || return 1
  jq -r '[.profiles[]?.roles?.backlog?.project_keys[]?] | unique | join("|")' \
    "$CONFIG_FILE" 2>/dev/null
}

TRACKER_KEYS=$(tracker_key_alternation) || TRACKER_KEYS=''

# ============================================================================
# AskUserQuestion: every distinct number referenced by bare "#N" must have a
# matching full URL (.../pull/N or .../issues/N) SOMEWHERE in the ask —
# per-NUMBER scope fix (2026-08-24, 4th recurrence of
# class=ask-option-pr-ref-missing-url).
#
# Two prior shapes were both wrong:
#   - payload-wide "any URL anywhere passes" (the original bug): a URL for
#     #22 in one option silently excused a DIFFERENT option's bare #13/#23/#17
#     with no URL at all — reproduced live in this recurrence.
#   - per-text-unit "the URL must sit in the exact same question/option text"
#     (a same-day fix attempt, caught by its own false-positive pass): the
#     common "question names the PR number, an option's description carries
#     the URL" pattern legitimately splits the number and its URL across two
#     units and got wrongly denied (sample: a "Merge PR #184?" question
#     plus a "Merge: https://.../pull/184" option).
# The correct scope is per NUMBER, not per URL-existence or per text unit:
# collect every number reached via bare "#N" anywhere in the ask, collect
# every number covered by a full URL anywhere in the ask, and require the
# first set to be a subset of the second — regardless of which unit each
# reference sits in.
# ============================================================================
check_ask_bare_ref() {
  local ask_text
  ask_text=$(echo "$INPUT" | jq -r '
    .tool_input.questions[]? |
    (.question // ""),
    (.options[]? | (.label // "") + ": " + (.description // ""))
  ' 2>/dev/null)

  [[ -z "$ask_text" ]] && return 0

  local bare_nums url_nums missing
  bare_nums=$(echo "$ask_text" | grep -oE "$BARE_REF_PATTERN" | tr -d '#' | sort -un)
  [[ -z "$bare_nums" ]] && return 0

  url_nums=$(echo "$ask_text" | grep -oE "$FULL_URL_PATTERN" | grep -oE '[0-9]+$' | sort -un)
  missing=$(comm -23 <(printf '%s\n' "$bare_nums") <(printf '%s\n' "$url_nums"))
  [[ -z "$missing" ]] && return 0

  {
    echo "DENIED: AskUserQuestion references a PR/issue by bare \"#N\" with no matching full URL anywhere in the ask."
    echo ""
    echo "Why blocked:"
    echo "  - The following number(s) appear as a bare \"#N\" but have NO"
    echo "    https://github.com/<owner>/<repo>/pull|issues/<N> URL for that SAME number"
    echo "    anywhere in this ask (a URL for a DIFFERENT number does not count):"
    echo "$missing" | sed 's/^/    - #/'
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Add the full URL for each missing number (in the same option or elsewhere in the ask)"
    echo "  2. Run \`gh pr view <N>\` / \`gh issue view <N>\` first to confirm the URL"
    echo "     before including it — do not fabricate one"
    echo ""
    echo "Reference: wip/resume.md \"Per-item direction ask\" Don't/Do row 6."
    echo "           failed-attempts.md \"ask-option-pr-ref-missing-url\" (4th recurrence)."
  } >&2
  exit 2
}

# ============================================================================
# AskUserQuestion: tracker item "<PROJECT>-<N>" without any clickable URL
# ============================================================================
check_ask_tracker_ref() {
  [[ -n "$TRACKER_KEYS" ]] || return 0

  local ask_text
  ask_text=$(echo "$INPUT" | jq -r '
    .tool_input.questions[]? |
    (.question // ""),
    (.options[]? | (.label // ""), (.description // ""))
  ' 2>/dev/null)

  [[ -z "$ask_text" ]] && return 0
  echo "$ask_text" | grep -qE "\b($TRACKER_KEYS)-[0-9]+\b" || return 0
  echo "$ask_text" | grep -qE "$ANY_URL_PATTERN" && return 0

  cat >&2 <<MSG
DENIED: AskUserQuestion references a tracker item without any clickable URL.

Why blocked:
  - The question text or an option's label/description contains a tracker
    reference matching: ($TRACKER_KEYS)-<N>
  - But no full URL (https://...) appears anywhere in this same ask

Why this matters:
  - A tracker key alone identifies nothing to the reader. Unlike a repo-local
    "#N", it cannot even be resolved by guessing the current repository, so
    the user is asked to decide about an item they cannot open or inspect.
  - The item's title is not a substitute: the ask must let the user verify the
    referenced item's own state before deciding.

Required action (pick one before retrying):
  1. Add the item's full tracker URL next to the reference
  2. If several tracker items appear, give each one its own URL
  3. Also state what the item actually is — a bare key plus a URL still hides
     the decision content the user needs

Project keys are read from: $CONFIG_FILE
  (union of every profile's roles.backlog.project_keys)
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
  AskUserQuestion)
    check_ask_bare_ref
    check_ask_tracker_ref
    ;;
  TaskCreate)       check_taskcreate_bare_ref ;;
esac

exit 0
