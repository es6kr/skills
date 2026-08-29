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

# Last assistant message (whole JSON entry)
LAST_MSG=$(jq -s 'map(select(.type == "assistant")) | last // empty' "$TRANSCRIPT" 2>/dev/null)
if [ -z "$LAST_MSG" ] || [ "$LAST_MSG" = "null" ]; then
  _log "early_exit=no_last_assistant_msg" "$TRANSCRIPT"
  exit 0
fi

# Concatenate all text-content from the assistant message
LAST_TEXT=$(echo "$LAST_MSG" | jq -r '.message.content // [] | map(select(.type == "text") | .text) | join("\n")' 2>/dev/null)
if [ -z "$LAST_TEXT" ]; then
  _log "early_exit=no_text_content" "$TRANSCRIPT"
  exit 0
fi

# Skip if AskUserQuestion was actually called in this response
ASK_COUNT=$(echo "$LAST_MSG" | jq -r '.message.content // [] | map(select(.type == "tool_use" and .name == "AskUserQuestion")) | length' 2>/dev/null)
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
