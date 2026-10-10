#!/usr/bin/env bash
# Stop event — Detect cleanup wrap-up / session-end report missing RAG visibility row
#
# Trigger: assistant response contains cleanup-completion or session-end markers
# Detection: response text matches cleanup keywords + missing distinct RAG visibility row ("RAG store N chunks" or "N chunks added")
# Action: emit {"decision":"block","reason":...} on stdout and exit 2. A Stop
#         hook cannot suppress the response already written, but this blocks the
#         stop and feeds `reason` back so the next turn re-surfaces the issue.
#         (The header previously described a non-blocking "exit 0" reminder,
#         which the block path at the bottom of this file has never done.)
#
# Background: failed-attempts.md — RAG report visibility missing 3 recurrences:
#   1st (2026-05-27): cleanup procedure compressed — 3-C.1 qdrant import deferred to ask
#   2nd (2026-06-15): cleanup wrap-up table missing RAG row
#   3rd (2026-06-16): session-end report had RAG row buried in prose (this hook trigger)
#
# Escalation policy (cleanup/run.md): 3rd recurrence+ Stop hook automation required.

# Ralph autonomous loop (RALPH_LOOP=1) manages RAG persistence via its own wrapper
# and has no interactive user to act on an injected reminder. Emitting the missing-RAG
# reminder every turn only adds noise the headless agent may fixate on, so pass silently.
if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

# Load locale-specific regex patterns from hook-kit/data/. The file is git-ignored
# so the public repo never sees Korean characters. When absent, cleanup detection
# falls back to English-only markers. The path stays hook-kit-relative because the
# regex data did not move when this guard was relocated into the cleanup skill.
HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
# Marker set kept IDENTICAL to the sibling guards (block-cleanup-missing-rename.sh,
# block-cleanup-missing-walkthrough.sh). It was previously a strict subset, on the
# reasoning that generic phrases produce false positives — but that cost more than
# it saved: run.md's mandatory-rows table applies the RAG-row obligation to the
# separate session-end report too ("## Session Ended"), and that is exactly the
# phrasing the siblings matched and this guard did not. The three guards therefore
# disagreed about whether the SAME report text was even in scope, which is its own
# failure class. Note the specific forms `Session Ended` / `Session Cleanup` /
# `session-end report` are matched — NOT the generic "End session" / "session end"
# that motivated the original narrowing, so that concern stays addressed. The real
# false-positive source was the response-extraction bug fixed below, not breadth.
#   - `/cleanup` (slash-command invocation, leading-boundary anchored)
#   - `cleanup run` (skill ARGUMENTS)
#   - `cleanup wrap-up` / `cleanup complete` / `cleanup pass` / `cleanup finished`
#   - `Session Ended` / `Session Cleanup` / `session-end report` (session-end report)
# Locale-specific marker variants (the wrap-up phrase and header marker in
# non-English locales) live in data/hangul-patterns.regex (HG_CLEANUP_MARKERS).
# Additive, not override (`:+…|` rather than `:-`) — the data file is sourced first,
# so `:-` let an untracked local file decide the whole marker set and silently retire
# the committed one. Union keeps the committed baseline authoritative; the git-ignored
# file only ADDS locale variants.
HG_CLEANUP_MARKERS="${HG_CLEANUP_MARKERS:+${HG_CLEANUP_MARKERS}|}(^|[[:space:]])/cleanup|cleanup run|cleanup wrap-up|cleanup complete|cleanup pass|cleanup finished|Session Ended|Session Cleanup|session-end report"
HG_CLEANUP_RAG_VISIBILITY="${HG_CLEANUP_RAG_VISIBILITY:+${HG_CLEANUP_RAG_VISIBILITY}|}chunks added|qdrant"
# Used only by the skipped-ingest branch at the bottom of this file. A report that
# declares the failure honestly is NOT the failure mode being guarded, so the
# failure vocabulary is checked first and wins over the success vocabulary.
HG_CLEANUP_SUCCESS_CLAIM="${HG_CLEANUP_SUCCESS_CLAIM:+${HG_CLEANUP_SUCCESS_CLAIM}|}(^|[^[:alnum:]_])(complete|completed|finished|Session Ended|success)([^[:alnum:]_]|$)"
HG_CLEANUP_FAILURE_CLAIM="${HG_CLEANUP_FAILURE_CLAIM:+${HG_CLEANUP_FAILURE_CLAIM}|}FAILED|failed|queued|pending-import|retry task"

INPUT=$(cat)

# Always extract TRANSCRIPT_PATH (needed for RAG-call detection later — not only
# for RESPONSE fallback). Earlier version scoped this inside `if [[ -z "$RESPONSE" ]]`
# which left TRANSCRIPT_PATH empty on the common path → HAS_RAG_CALL silently stayed 0.
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Extract assistant message text from Stop event payload
RESPONSE=$(echo "$INPUT" | jq -r '
  .response // .transcript // .assistant_message // empty
' 2>/dev/null)

# Fallback: try parsing transcript-based payload (varies by Stop hook implementation)
if [[ -z "$RESPONSE" ]] && [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  # Read the LAST assistant turn only — same extraction as the sibling guards
  # (block-cleanup-missing-rename.sh / block-cleanup-missing-walkthrough.sh).
  # The earlier form `jq -r 'select(...)' | tail -100` was a false-positive
  # generator in two distinct ways, because it concatenated the text of EVERY
  # assistant message in the window and then truncated that blob:
  #   1. a cleanup marker emitted in an EARLIER turn kept the trigger gate open,
  #      so ordinary mid-work progress messages were judged to be completion
  #      reports and re-blocked every turn (the "sticky re-firing" symptom);
  #   2. `tail -100` dropped the top of a long report, so a COMPLIANT report
  #      whose 3-C.1 RAG row sat above the last 100 lines was read as having no
  #      RAG row at all — which is why emitting the RAG line on its own (a short
  #      response, never truncated) was the only reliable way through.
  # Slurping and taking `last` scopes the verdict to the response actually being
  # judged, and removes the truncation entirely.
  RESPONSE=$(tail -50 "$TRANSCRIPT_PATH" | jq -rs '([.[] | select(.type=="assistant")] | last) as $m | ($m.message.content[]?.text? // empty)' 2>/dev/null)
fi

if [[ -z "$RESPONSE" ]]; then
  exit 0
fi

# Detect cleanup-completion or session-end markers (locale variants from data/)
if ! echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_MARKERS"; then
  exit 0
fi

# Detect distinct RAG visibility row (must appear as a TABLE ROW or BOLD line,
# not buried in prose). Heuristics:
#   1. Markdown table row whose LABEL CELL (first cell after the leading |) is
#      RAG-related — not just any cell in the row. A row labeled "BLOCKED" or
#      "Commits" that happens to mention "qdrant"/"chunks" as a supporting
#      detail must NOT satisfy this check (4th recurrence — a BLOCKED row
#      containing a "qdrant readyz 200 ... N chunks" prose justification
#      passed the old any-cell regex and buried the real count).
#   2. Bold line "**chunks added**" / "**qdrant**" / locale variant
#   3. Header-like "### RAG" / "## RAG"
HAS_RAG_ROW=0
if echo "$RESPONSE" | grep -qE '^\s*\|\s*\*{0,2}[^|]*(RAG|qdrant|3-C\.1)[^|]*\*{0,2}\s*\|.*(RAG|qdrant|chunks)'; then
  HAS_RAG_ROW=1
elif echo "$RESPONSE" | grep -qE "\*\*.*($HG_CLEANUP_RAG_VISIBILITY).*\*\*"; then
  HAS_RAG_ROW=1
elif echo "$RESPONSE" | grep -qE '^#{2,3}\s+.*(RAG|qdrant)'; then
  HAS_RAG_ROW=1
fi

if [[ "$HAS_RAG_ROW" -eq 1 ]]; then
  exit 0
fi

# Detect that RAG store actually happened in this session.
# Match must be a tool_use entry (actual call), not prose mention/quoted skill body.
# Without parsing entry types, plain `grep qdrant-import` matches assistant text
# that merely cites the skill (e.g., quoting cleanup/run.md inline) — false positive.
HAS_RAG_CALL=0
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
  # Parse jsonl: select assistant tool_use entries → inspect Bash command + MCP tool name.
  # Falls back silently if jq fails (HAS_RAG_CALL stays 0 = hook exits OK = no false block).
  if jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | (.name + " " + (.input.command? // ""))' "$TRANSCRIPT_PATH" 2>/dev/null \
       | grep -qE 'qdrant-import\.py|mcp__qdrant__|qdrant-store|qdrant_store' 2>/dev/null; then
    HAS_RAG_CALL=1
  fi
fi

if [[ "$HAS_RAG_CALL" -eq 0 ]]; then
  # No ingest ran at all. This used to exit silently, which left the ROOT cause of
  # failed-attempts.md "cleanup-mandatory-three-reports-omission" unguarded: the
  # report omits the RAG row precisely BECAUSE the ingest was skipped, so there is
  # no receiver call for the branch above to notice.
  #
  # Deliberately narrow (user decision 2026-10-07): block only a finished-looking
  # report that CLAIMS SUCCESS. run.md is explicit that a FAILED RAG row makes the
  # whole run FAILED and that "✅ Complete" must not then be declared — asserting
  # success with no row at all is strictly worse than declaring FAILED. Anything
  # that is mid-progress, or that reports the failure honestly, is left alone, so
  # workspaces with no RAG receiver are not punished for saying so.
  if ! echo "$RESPONSE" | grep -qE '^[[:space:]]*\|'; then
    exit 0   # not a report table — mid-cleanup progress message
  fi
  # Failure vocabulary alone (e.g. a Tests row saying "0 failed") is not a
  # cleanup/RAG failure declaration. Require the failure status on its subject.
  if echo "$RESPONSE" | grep -qiE "(cleanup([[:space:]]+(run|wrap-up))?|RAG([[:space:]]+(store|ingest|import))?)[[:space:]:*|=-]+($HG_CLEANUP_FAILURE_CLAIM)([^[:alnum:]_]|$)"; then
    exit 0   # cleanup/RAG failure declared honestly; nothing to hide
  fi
  if ! echo "$RESPONSE" | grep -qiE "$HG_CLEANUP_SUCCESS_CLAIM"; then
    exit 0   # no success claim
  fi
  cat <<'SKIPPED_EOF'
{
  "decision": "block",
  "reason": "Cleanup/session-end report claims success, carries no RAG visibility row, and this session made no RAG receiver call at all -- so the 3-C.1 ingest was skipped, not merely under-reported. cleanup/run.md: the 3-C.1 row is mandatory, 'RAG store failure = cleanup failure', and a step-level skip is valid ONLY when that step's own documented skip-condition text is quoted alongside it. Do one of: (a) run the ingest and report `| **3-C.1 RAG Store** | **N chunks added (receiver: <vendor>) -- session UUID <uuid>** |`, (b) if it genuinely failed, report `FAILED -- queued to the local pending-import queue, retry task registered` and change the header to 'cleanup FAILED' rather than claiming success, or (c) if this workspace has no receiver, state that outcome in the 3-C.1 row itself instead of omitting the row."
}
SKIPPED_EOF
  exit 2
fi

# RAG was invoked + cleanup/session-end marker present + no visibility row
# → emit reminder. Stop hook accepts JSON output with `additionalContext` to inject.
cat <<'EOF'
{
  "decision": "block",
  "reason": "Cleanup/session-end report detected but RAG store result is not highlighted as a separate row/bold/header. failed-attempts.md \"cleanup report RAG visibility missing\" 3rd-recurrence escalation hook triggered. The next response MUST include the RAG store result in one of these formats: (a) separate markdown table row: `| **3-C.1 RAG store** | **N chunks added (receiver: <vendor>)** |` OR (b) bold line: `**RAG store summary: N chunks added (receiver: <vendor>) — session UUID <uuid>**` OR (c) separate header section `### RAG store`. Burying it as one line inside a prose list is forbidden."
}
EOF
exit 2
