#!/usr/bin/env bash
# Stop event — Detect cleanup wrap-up / session-end report missing the mandatory
# cleanup-procedure Skill calls: Skill("cleanup") itself + Skill("claudify", improve/persist)
#
# Two detection gates:
#   Gate B (primary, structural): the transcript contains a genuine `/cleanup`
#     slash-command invocation (user-typed line, NOT a tool_result quote) within
#     the recent window — scope ALL checks to the segment AFTER that line and
#     require (a) a real `Skill("cleanup")` tool_use AND (b) claudify improve +
#     persist tool_use traces in that segment.
#   Gate A (fallback, text markers): no in-window command anchor, but the last
#     assistant response carries cleanup-completion markers — legacy whole-
#     transcript claudify check (free-text cleanup invocations).
#
# Action: emit reminder via stdout (decision:block, exit 0). Stop hooks only
# have their stdout JSON decision parsed on exit 0 — exit 2 discards stdout
# and reads stderr instead, silently dropping the crafted "reason" text.
#
# Background: failed-attempts.md — cleanup claudify Skill call omission recurrences:
#   1st (2026-05-27): cleanup procedure compressed — claudify improve never invoked
#   2nd (2026-06-15): cleanup wrap-up replaced claudify persist with inline retrospect
#   3rd (2026-06-22): Step 2/3 channel filled with inline matrix text + RAG-only Skill call
#   4th (2026-07-17): detection regex false-positived on claudify's OWN free-text skill
#     description recurring in "available skills" system-reminder blocks — fixed by
#     anchoring on the quoted `"skill":"claudify"` key-value pair (tool_use input only).
#   5th (2026-07-18): TWO gaps let an ad-hoc cleanup slip through silently:
#     (a) marker list missed report variants with words between "cleanup" and the
#         completion keyword (e.g. a step-count phrase in the middle), and
#     (b) checks scanned the WHOLE transcript — a proper cleanup run earlier in the
#         same session left claudify traces that satisfied the check for a later
#         ad-hoc cleanup. Fixed by Gate B: anchor on the LAST genuine /cleanup
#         slash-command line and scope all checks AFTER it. Anchor excludes
#         tool_result user-lines (RAG results quoting other sessions' /cleanup)
#         and assistant lines (escaped quotes never match the structural pattern).
#   6th (2026-07-27): Gate B's anchor matched a `<command-name>/cleanup</command-name>`
#     substring embedded as narrative text INSIDE a compact-summary message
#     (`"isCompactSummary":true`) — the summary quotes prior turns verbatim while
#     describing "all user messages," so a genuinely-completed /cleanup from before
#     a compact reads identically to a live re-invocation. Compaction also erases the
#     Skill tool_use evidence for calls that really did happen pre-compact, so
#     "missing after this anchor" is structurally unverifiable, not necessarily true.
#     Fixed two ways: (a) exclude isCompactSummary lines from the anchor grep — a
#     summary's own narrative is never a live invocation; (b) when a genuine anchor
#     IS found but a compact boundary sits between it and now, emit an ask-required
#     reason instead of an unconditional block — the assistant must confirm with the
#     user whether to redo Self-Improve/Knowledge Persist, since pre-compact
#     completion can no longer be independently verified either way.
#
# Escalation policy (cleanup/run.md): 3rd recurrence+ Stop hook automation required.

# Ralph autonomous loop (RALPH_LOOP=1) manages self-improvement/persistence via its
# own wrapper, not the claudify skill, and has no interactive user to re-invoke it.
if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

# Lines of transcript after the /cleanup invocation within which Gate B stays
# active. Beyond this, the session has long moved on — Gate A may still fire.
GATEB_WINDOW=2500

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public repo never sees Korean characters. When absent, cleanup detection
# falls back to English-only markers.
HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
# NOTE: do not use ${VAR:-default} here — a `}` inside the regex quantifier
# ({0,20}) terminates the parameter expansion early and corrupts the pattern.
if [[ -z "${HG_CLEANUP_MARKERS:-}" ]]; then
  HG_CLEANUP_MARKERS='cleanup run|(^|[[:space:]])/cleanup|cleanup wrap-up'
fi

INPUT=$(cat)

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Extract assistant message text from Stop event payload (Gate A input)
RESPONSE=$(echo "$INPUT" | jq -r '
  .response // .assistant_message // empty
' 2>/dev/null)
if [[ -z "$RESPONSE" ]] && [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  RESPONSE=$(tail -50 "$TRANSCRIPT_PATH" | jq -rs '([.[] | select(.type=="assistant")] | last) as $m | ($m.message.content[]?.text? // empty)' 2>/dev/null)
fi

# Helper: extract claudify call flags from a stream on stdin.
# STRUCTURAL match only: `"skill":"claudify"` appears ONLY inside a real Skill
# tool_use `input` object. Free-text mentions are JSON-escaped (\") and never match.
check_claudify_calls() {
  local segment="$1"
  HAS_CLAUDIFY_IMPROVE=0
  HAS_CLAUDIFY_PERSIST=0
  local calls
  calls=$(echo "$segment" | grep -oE '"skill":"([^"]*:)?claudify"[^}]*}' 2>/dev/null)
  if echo "$calls" | grep -qE '"args":"[^"]*improve'; then HAS_CLAUDIFY_IMPROVE=1; fi
  if echo "$calls" | grep -qE '"args":"[^"]*persist'; then HAS_CLAUDIFY_PERSIST=1; fi
}

emit_block() {
  local missing="$1" context="$2"
  # Build JSON via jq so quotes inside the reason are escaped correctly.
  jq -n --arg reason "Cleanup detected (${context}) but the following Skill call(s) are missing from the relevant transcript segment: ${missing}. A slash-command inject is NOT a Skill invocation (skill-usage.md HARD STOP) — the procedure starts only with a real Skill tool call. cleanup/run.md requires Skill(\"cleanup\") to enter the procedure, Skill(\"claudify\", \"improve\") for Step 2 (Self-Improve), and Skill(\"claudify\", \"persist\") for Step 3 (Knowledge Persist). Inline retrospect/persist text in a summary matrix DOES NOT count. The next response MUST invoke the missing Skill(s) and follow run.md before declaring cleanup complete." \
    '{decision: "block", reason: $reason}'
  exit 0
}

# 6th recurrence fix: a genuine anchor was found, but a compact/rewind boundary
# sits between it and now — pre-compact completion is unverifiable in EITHER
# direction (it may really be done, or really missing). Require an explicit
# user decision instead of forcing blind re-execution.
emit_ask_required() {
  local missing="$1"
  jq -n --arg reason "Cleanup was invoked, but a compact/rewind boundary occurred before the following Skill call(s) could be verified in the transcript: ${missing}. A compact erases Skill tool_use evidence even when the work genuinely completed pre-compact, so 'missing' here does not mean 'never done.' Do NOT blindly re-run the full Self-Improve/Knowledge Persist procedure, and do NOT silently skip it either — call AskUserQuestion first: state that a compact boundary makes pre-compact completion unverifiable, and ask whether to redo Skill(\"claudify\", \"improve\")/Skill(\"claudify\", \"persist\") now or treat the prior summary's claim as sufficient. Proceed only per the user's choice." \
    '{decision: "block", reason: $reason}'
  exit 0
}

# ---------- Gate B: /cleanup slash-command anchor (primary, structural) ----------
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  # Genuine invocation line: user-typed slash command. Excludes (a) tool_result
  # user-lines (RAG/search results quoting another session's invocation), (b)
  # assistant lines (their inner quotes are JSON-escaped so the unescaped
  # `"type":"user"` pattern never matches them), and (c) compact-summary lines
  # (`"isCompactSummary":true`) — a summary's own narrative quotes prior turns
  # verbatim (e.g. "all user messages" recaps), so it can contain the literal
  # tag text without being a live re-invocation (6th recurrence).
  CLEANUP_CMD_LINE=$(grep -n '<command-name>/cleanup' "$TRANSCRIPT_PATH" 2>/dev/null \
    | grep '"type":"user"' | grep -v 'tool_result' | grep -v '"isCompactSummary":true' \
    | tail -1 | cut -d: -f1)
  if [[ -n "$CLEANUP_CMD_LINE" ]]; then
    TOTAL_LINES=$(wc -l < "$TRANSCRIPT_PATH")
    if (( TOTAL_LINES - CLEANUP_CMD_LINE <= GATEB_WINDOW )); then
      SCOPED=$(tail -n +"$CLEANUP_CMD_LINE" "$TRANSCRIPT_PATH")
      MISSING=""
      if ! echo "$SCOPED" | grep -qE '"skill":"([^"]*:)?cleanup"'; then
        MISSING="${MISSING}Skill(\"cleanup\"), "
      fi
      check_claudify_calls "$SCOPED"
      if [[ "$HAS_CLAUDIFY_IMPROVE" -eq 0 ]]; then
        MISSING="${MISSING}Skill(\"claudify\", \"improve\"), "
      fi
      if [[ "$HAS_CLAUDIFY_PERSIST" -eq 0 ]]; then
        MISSING="${MISSING}Skill(\"claudify\", \"persist\"), "
      fi
      MISSING="${MISSING%, }"
      if [[ -n "$MISSING" ]]; then
        # A compact/rewind boundary between the genuine anchor and now means the
        # "missing" calls may have really happened pre-compact — their tool_use
        # evidence just didn't survive compaction. Ask instead of forcing.
        if echo "$SCOPED" | grep -q '"isCompactSummary":true'; then
          emit_ask_required "$MISSING"
        fi
        emit_block "$MISSING" "slash-command /cleanup invoked; checks scoped after the last invocation"
      fi
      exit 0
    fi
  fi
fi

# ---------- Gate A: response-marker fallback (free-text cleanup, no command anchor) ----------
if [[ -z "$RESPONSE" ]]; then
  exit 0
fi
if ! echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_MARKERS"; then
  exit 0
fi

if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  check_claudify_calls "$(cat "$TRANSCRIPT_PATH")"
else
  HAS_CLAUDIFY_IMPROVE=0
  HAS_CLAUDIFY_PERSIST=0
fi

if [[ "$HAS_CLAUDIFY_IMPROVE" -eq 1 ]] && [[ "$HAS_CLAUDIFY_PERSIST" -eq 1 ]]; then
  exit 0
fi

MISSING=""
if [[ "$HAS_CLAUDIFY_IMPROVE" -eq 0 ]]; then
  MISSING="${MISSING}Skill(\"claudify\", \"improve\"), "
fi
if [[ "$HAS_CLAUDIFY_PERSIST" -eq 0 ]]; then
  MISSING="${MISSING}Skill(\"claudify\", \"persist\"), "
fi
MISSING="${MISSING%, }"
emit_block "$MISSING" "cleanup-completion markers in the last response"
