#!/usr/bin/env bash
# Stop event — Detect a cleanup/session-end completion report that includes
# the "Session ID:" identity line but omits the accompanying `/rename`
# recommendation (2-3 candidates) required by cleanup/run.md Step 5's
# "Session identity (mandatory)" row.
#
# Trigger: assistant response contains cleanup-completion or session-end markers
#          AND a "Session ID:" line
# Detection: no `/rename ` command token anywhere in the same response.
# Locale-specific marker variants live in data/hangul-patterns.regex
# (git-ignored — this repo is PUBLIC, English-only source).
# Action: emit reminder via stdout (non-blocking read, but exit 2 blocks Stop
#         and injects context for the next turn).
#
# Background: failed-attempts.md "cleanup-procedure" class, 11th recurrence —
# the Session-identity row's rename-candidate sub-clause had zero mechanical
# backstop (existing sibling hooks only cover RAG/claudify/skip-condition
# sub-rows), so it kept getting dropped when a cleanup report was composed
# from memory of a prior pass instead of re-reading run.md's literal template.
#
# Escalation policy (cleanup/run.md): cleanup-procedure class already
# hook-active for 2 mechanisms; this is a 3rd mechanism for the same class.

if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi

# Completion phrasings are included deliberately: a real wrap-up report is far
# more likely to be headed "cleanup complete" / "cleanup pass 2 complete" than
# to repeat the literal invocation "/cleanup run", and those natural headings
# previously matched nothing here, so the guard never even entered its checks.
# Additive, not override (`:+…|` rather than `:-`). The locale data file is sourced
# first, so with `:-` its value REPLACED everything below and the committed markers
# became dead code on any machine that has the file — `Session Cleanup` here was
# live in the repo and silently absent in practice. Which set wins should not depend
# on whether an untracked file happens to exist. Union keeps the committed baseline
# authoritative and lets the git-ignored file only ADD locale variants.
HG_CLEANUP_MARKERS="${HG_CLEANUP_MARKERS:+${HG_CLEANUP_MARKERS}|}(^|[[:space:]])/cleanup|cleanup run|cleanup wrap-up|cleanup complete|cleanup pass|cleanup finished|Session Ended|Session Cleanup|session-end report"
HG_SESSION_ID_MARKERS="${HG_SESSION_ID_MARKERS:+${HG_SESSION_ID_MARKERS}|}Session ID:|session[[:space:]]+id:"
# Words that, together with a markdown table, mark a response as the completion
# report itself rather than a mid-cleanup progress message. Used only to decide
# whether an ABSENT Session ID line is already due (see the omission branch).
HG_COMPLETION_WORDS="${HG_COMPLETION_WORDS:+${HG_COMPLETION_WORDS}|}complete|completed|finished|Session Ended|wrap-up"
# Row labels unique to run.md's Step 5 mandatory-rows table. Requiring one of
# these keeps the omission branch off unrelated "<something> cleanup finished"
# reports that merely happen to contain a table (e.g. a file-cleanup summary).
HG_CLEANUP_STEP_ROWS="${HG_CLEANUP_STEP_ROWS:+${HG_CLEANUP_STEP_ROWS}|}Self-Improve|Knowledge Persist|RAG Store|wip task|TaskList|Task prune|Weekly Report"

INPUT=$(cat)

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

RESPONSE=$(echo "$INPUT" | jq -r '
  .response // .transcript // .assistant_message // empty
' 2>/dev/null)

if [[ -z "$RESPONSE" ]] && [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  RESPONSE=$(tail -50 "$TRANSCRIPT_PATH" | jq -rs '([.[] | select(.type=="assistant")] | last) as $m | ($m.message.content[]?.text? // empty)' 2>/dev/null)
fi

if [[ -z "$RESPONSE" ]]; then
  exit 0
fi

# Only fire on cleanup/session-end context responses
if ! echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_MARKERS"; then
  exit 0
fi

# A cleanup response that never reaches Step 5 is not a violation of this row
# yet — that is why an absent Session ID line cannot simply be treated as a
# violation. But the original "absent => always exit 0" rule left the most
# common failure mode silent: dropping the ENTIRE row from a finished report
# passed, while writing it partially (ID without /rename) was caught. Split the
# two cases: still exempt mid-cleanup progress messages, but treat the omission
# as a violation once the response is clearly the completion report itself
# (a markdown table plus completion wording).
if ! echo "$RESPONSE" | grep -qiE "$HG_SESSION_ID_MARKERS"; then
  if echo "$RESPONSE" | grep -qE '^[[:space:]]*\|' \
     && echo "$RESPONSE" | grep -qiE "$HG_COMPLETION_WORDS" \
     && echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_STEP_ROWS"; then
    cat <<'EOF'
{
  "decision": "block",
  "reason": "Cleanup/session-end completion report omits the 'Session identity (mandatory)' row entirely — no `Session ID:` line and therefore no `/rename` candidates either. cleanup/run.md Step 5's mandatory-rows table requires this row in BOTH the cleanup wrap-up table and any separate session-end report. Re-read that section's literal row text (do not reconstruct the table from memory of a prior pass — it silently drops rows) and re-emit the report with every mandatory row present: Session identity, 0 TaskList, 1 Commit, 2 Self-Improve, 3 Knowledge Persist, 3-C.1 RAG Store (separate row), 3-C.2 structured discovery chunk, 3-C.4 fix_plan sync when applicable, 4 Weekly Report, 5 wip task registration."
}
EOF
    exit 2
  fi
  exit 0
fi

# The row is satisfied only by an EXECUTABLE candidate: `/rename` followed by a
# name token the user can copy-paste as-is. Requiring merely the `/rename` token
# let "/rename recommended" style prose through — the token was present, the
# candidate was not (failed-attempts.md "cleanup-report-chunk-and-rename-omission"
# 21st recurrence: the row read "`/rename` <recommended>" with no name at all).
# A session name is ASCII (model-topic-sessid8), so any non-ASCII word following
# the token is prose, not a candidate.
if echo "$RESPONSE" | grep -qE "/rename[[:space:]]+[A-Za-z0-9][A-Za-z0-9._-]{2,}"; then
  exit 0
fi

cat <<'EOF'
{
  "decision": "block",
  "reason": "Cleanup/session-end report includes a 'Session ID:' line but no accompanying `/rename <model>-<topic>-<sessid8>` recommendation (2-3 candidates). cleanup/run.md Step 5's 'Session identity (mandatory)' row requires both together — re-read the row's literal text (do not reconstruct it from memory of a prior pass) and add the rename candidates as standalone `/rename ...` code spans (no label/colon inside the span, so a single copy-paste is directly runnable)."
}
EOF
exit 2
