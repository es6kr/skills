#!/usr/bin/env bash
# Stop hook — detect AskUserQuestion bypass via delegation/next-step text framing.
#
# Trigger: last assistant text contains delegation/decision keywords + bullet/numbered list >=2
#          AND same response has NO AskUserQuestion tool_use.
# Action: emit {"decision":"block","reason":"..."} — Stop event schema does NOT
#         support hookSpecificOutput.additionalContext (6th 2026-06-13: schema
#         validation failure observed; only UserPromptSubmit/PostToolUse/PostToolBatch
#         accept additionalContext). decision:"block"+reason mirrors next-trigger.sh
#         and trigger-Stop.sh: blocks Stop, feeds reason text back to the LLM.
#
# Background: failed-attempts.md "Option-table text awaiting decision — AskUserQuestion bypass"
#             (1st 2026-05-28: option A/B/C/D table, 2nd 2026-05-29: guidance-style wrap-up,
#              3rd 2026-06-11: activation step progress guidance). 3rd recurrence triggered
#             fix.md "Hook deferral forbidden" — hook implemented.
#             4th 2026-06-12 conditional deferral ("on separate instruction I will ~") —
#             post-hook miss (regex gap). Pattern strengthened. See failed-hooks.md.
#             5th 2026-06-12 direct interrogative offer ("shall I also check settings.json?")
#             — hook was UNREGISTERED in settings.json + single interrogative escaped the
#             list>=2 gate. Registered in Stop + INTERROGATIVE_PATTERN added. See failed-hooks.md.
#
#             22nd 2026-08-13: a direct-answer response ending on a bare trailing
#             "?" (a small disambiguation question) did NOT block live, even though
#             offline replay of the exact transcript state through this script
#             correctly returned decision:block — matching logic + settings.json
#             registration both confirmed intact. Root cause of the live miss
#             unconfirmed (no prior invocation trail to inspect). Added per-invocation
#             debug logging (check-ask-bypass-keywords.debug.log, mirrors
#             next-trigger.sh) so the next live miss has direct evidence instead of
#             requiring offline reconstruction.
#
# Cannot block the response itself (Stop hook fires after the response ends).
# Reminder is injected so the NEXT turn does the AskUserQuestion call.

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public repo never sees Korean characters. When absent, the keyword +
# interrogative patterns fall back to never-match so the hook is a no-op (no
# bypass detection in non-Korean environments). This is intentional — the hook
# protects against Korean phrasing patterns specifically.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_BYPASS_KEYWORD_PATTERN="${HG_BYPASS_KEYWORD_PATTERN:-__NEVER_MATCH__}"
HG_BYPASS_INTERROGATIVE_PATTERN="${HG_BYPASS_INTERROGATIVE_PATTERN:-__NEVER_MATCH__}"
HG_BYPASS_CONDITIONAL_DEFERRAL_PATTERN="${HG_BYPASS_CONDITIONAL_DEFERRAL_PATTERN:-__NEVER_MATCH__}"
LOCALE_DATA_PRESENT=1
[ -f "$HG_DATA_FILE" ] || LOCALE_DATA_PRESENT=0
ENGLISH_CONDITIONAL_DEFERRAL_PATTERN='(let me know|if you('\''d like| want| prefer)|on your instruction|whenever you('\''re| are) ready|if needed).*(I will|we can|I'\''ll|proceed)'

# Debug log of this hook's own invocations — mirrors next-trigger.sh's
# next-trigger.debug.log. Added after a live-miss (failed-attempts.md
# "ask-text-question" 22nd recurrence) where the hook, empirically re-run offline
# against the exact transcript state, correctly returned decision:block —
# yet no block occurred in the live session. Without a per-invocation trail,
# that class of miss can only be diagnosed by slow after-the-fact
# reconstruction. Self-trims at 500 lines, keeps last 200 (same policy as
# next-trigger.sh).
DEBUG_LOG="$(dirname "$0")/check-ask-bypass-keywords.debug.log"
_log() { { printf '%s\t%s\ttranscript=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >> "$DEBUG_LOG"; } 2>/dev/null || true; }

INPUT=$(cat)

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
if [ ! -f "$TRANSCRIPT" ]; then
  _log "early_exit=no_transcript" "$TRANSCRIPT"
  exit 0
fi

# Assistant entries belonging to the CURRENT turn — everything after the last
# user entry. Reading only the final assistant entry misses any turn that ends
# with a tool_use-only block: the prose sits in an earlier entry of the same
# turn, so the hook early-exited as no_text_content and never evaluated the
# text at all (2 of the first 3 logged invocations took that path, while the
# turn they belonged to did end in prose).
TURN=$(jq -s '
  . as $all
  | ([range(0; ($all | length)) | select($all[.].type == "user")] | last) as $u
  | (if $u == null then $all else $all[($u + 1):] end)
  | map(select(.type == "assistant"))
' "$TRANSCRIPT" 2>/dev/null)
if [ -z "$TURN" ] || [ "$TURN" = "null" ] || [ "$TURN" = "[]" ]; then
  _log "early_exit=no_last_assistant_msg" "$TRANSCRIPT"
  exit 0
fi

# The last NON-EMPTY text block of the turn — i.e. the prose the user actually
# read last. Keeping "last block" rather than "all blocks joined" preserves the
# trailing-question-mark check's original scope.
LAST_TEXT=$(echo "$TURN" | jq -r '
  map(.message.content // [] | map(select(.type == "text") | .text) | join("\n"))
  | map(select(length > 0))
  | last // ""
' 2>/dev/null)
if [ -z "$LAST_TEXT" ]; then
  _log "early_exit=no_text_content" "$TRANSCRIPT"
  exit 0
fi

# Skip if AskUserQuestion was called ANYWHERE in this turn. Scoping this to the
# same turn (not one entry) is what makes the widened text scope safe: a turn
# whose prose and whose ask sit in different entries must not be flagged.
ASK_COUNT=$(echo "$TURN" | jq -r '
  [.[] | .message.content // [] | .[] | select(.type == "tool_use" and .name == "AskUserQuestion")] | length
' 2>/dev/null)
if [ -n "$ASK_COUNT" ] && [ "$ASK_COUNT" != "0" ]; then
  _log "early_exit=ask_already_called ask_count=$ASK_COUNT" "$TRANSCRIPT"
  exit 0
fi

# Keyword patterns sourced from data/hangul-patterns.regex
#   HG_BYPASS_KEYWORD_PATTERN              — delegation / next-step framing
#   HG_BYPASS_INTERROGATIVE_PATTERN        — direct action-offer interrogative
#   HG_BYPASS_CONDITIONAL_DEFERRAL_PATTERN — conditional deferral in prose endings
# When the data file is absent they fall back to __NEVER_MATCH__ so the hook
# becomes a no-op (intentional — bypass framing is locale-specific).

# Language-agnostic trailing-question-mark check — the response's last
# non-whitespace character is "?"/"？". Catches any interrogative ending
# (Korean or English) without relying on an enumerated verb/ending list, which
# 14 prior recurrences showed always misses the next novel phrasing (see
# failed-attempts.md "ask-text-question" class). Scoped to the LAST LINE only
# (not the whole response) to keep the false-positive surface bounded — a
# question mark earlier in the body (e.g. a quoted question being analyzed)
# does not trigger this.
LAST_LINE=$(printf '%s' "$LAST_TEXT" | tail -n 1)
TRAILING_QUESTION=0
if printf '%s' "$LAST_LINE" | grep -qE '[?？][[:space:]"'"'"']*$'; then
  TRAILING_QUESTION=1
fi

# Locale data absent -> every HG_BYPASS_* pattern is __NEVER_MATCH__ and this
# hook silently detects nothing but the English regex and a trailing "?".
# That silence is what let the plain-text-deferral class reach 13 recurrences:
# the guard looked installed and registered while being a no-op. Surface it
# once per session so a missing data/ file cannot go unnoticed for months.
if [ "$LOCALE_DATA_PRESENT" = "0" ]; then
  _log "warn=locale_data_absent file=$HG_DATA_FILE" "$TRANSCRIPT"
  SESSION_KEY=$(basename "$TRANSCRIPT" .jsonl)
  # Marker lives in the OS temp dir, not the repo tree — it is ephemeral
  # session state, and writing it beside the script leaves untracked files
  # behind on every run (including test runs).
  WARN_MARKER="${TMPDIR:-/tmp}/ask-bypass-locale-warned-$SESSION_KEY"
  if [ ! -f "$WARN_MARKER" ]; then
    : > "$WARN_MARKER" 2>/dev/null || true
    jq -n --arg f "$HG_DATA_FILE" '{
      decision: "block",
      reason: ("[hook:check-ask-bypass-keywords] Locale pattern data is MISSING: \($f)\n\nEvery HG_BYPASS_* pattern has fallen back to __NEVER_MATCH__, so this hook currently detects only the English deferral regex and a bare trailing \"?\". Locale-specific text-question detection is OFF.\n\nThe file is machine-local by design (.gitignore `skills/*/data`) — it is not restored by pulling. Rebuild it, then re-run skills/hook-kit/tests/test-check-ask-bypass-keywords.sh to confirm the patterns load.\n\nThis notice fires once per session.")
    }'
    exit 0
  fi
fi

MATCH_REASON=""
if [ "$TRAILING_QUESTION" = "1" ]; then
  # Bare trailing "?" on the last line — fire regardless of keyword/list gates.
  MATCH_REASON="trailing_question_mark"
elif echo "$LAST_TEXT" | grep -qE "$HG_BYPASS_INTERROGATIVE_PATTERN"; then
  # Direct interrogative offer — fire regardless of list count.
  MATCH_REASON="interrogative_offer"
elif echo "$LAST_TEXT" | grep -qE "$HG_BYPASS_CONDITIONAL_DEFERRAL_PATTERN" || echo "$LAST_TEXT" | grep -iqE "$ENGLISH_CONDITIONAL_DEFERRAL_PATTERN"; then
  # Conditional deferral without list count requirement — catches prose endings.
  MATCH_REASON="conditional_deferral"
elif echo "$LAST_TEXT" | grep -qE "$HG_BYPASS_KEYWORD_PATTERN"; then
  # Delegation/next-step framing — require bullet/numbered list >= 2 (cuts FP).
  LIST_COUNT=$(echo "$LAST_TEXT" | grep -cE '^[[:space:]]*([0-9]+\.|[-*])[[:space:]]+')
  if [ "$LIST_COUNT" -lt 2 ]; then
    _log "pass=keyword_matched_but_list_count_below_2 list_count=$LIST_COUNT" "$TRANSCRIPT"
    exit 0
  fi
  MATCH_REASON="delegation_keyword_list>=2"
else
  _log "pass=no_pattern_matched" "$TRANSCRIPT"
  exit 0
fi

_log "BLOCK reason=$MATCH_REASON" "$TRANSCRIPT"

# Trim to last 200 lines once the log exceeds 500 (same policy as next-trigger.sh)
if [ "$(wc -l < "$DEBUG_LOG" 2>/dev/null || echo 0)" -gt 500 ]; then
  tail -n 200 "$DEBUG_LOG" > "$DEBUG_LOG.tmp" 2>/dev/null && mv "$DEBUG_LOG.tmp" "$DEBUG_LOG" 2>/dev/null
fi

REMINDER="[hook:check-ask-bypass-keywords] Text-question pattern detected (last line ends with a bare '?', conditional deferral in prose, delegation/next-step framing + list>=2, or direct interrogative offer) + no AskUserQuestion call in the same response.

ask-user-question.md \"Questions must use the AskUserQuestion tool — text questions are forbidden\" rule applies. If a user-decision axis is identified, call AskUserQuestion instead of writing a text prompt.

Self-check (at the start of the next turn):
1. Did the previous response contain an axis requiring user decision?
2. If yes, call AskUserQuestion as the first action (pre-validate option descriptions + split axes)
3. If no axis exists, ignore

Details: ~/.agents/rules/ask-user-question.md, ~/.claude/skills/cleanup/data/failed-attempts.md \"Option-table text awaiting decision\""

jq -n --arg msg "$REMINDER" '{
  decision: "block",
  reason: $msg
}'
exit 0
