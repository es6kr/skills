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

INPUT=$(cat)

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -f "$TRANSCRIPT" ] || exit 0

# Last assistant message (whole JSON entry)
LAST_MSG=$(jq -s 'map(select(.type == "assistant")) | last // empty' "$TRANSCRIPT" 2>/dev/null)
if [ -z "$LAST_MSG" ] || [ "$LAST_MSG" = "null" ]; then
  exit 0
fi

# Concatenate all text-content from the assistant message
LAST_TEXT=$(echo "$LAST_MSG" | jq -r '.message.content // [] | map(select(.type == "text") | .text) | join("\n")' 2>/dev/null)
[ -z "$LAST_TEXT" ] && exit 0

# Skip if AskUserQuestion was actually called in this response
ASK_COUNT=$(echo "$LAST_MSG" | jq -r '.message.content // [] | map(select(.type == "tool_use" and .name == "AskUserQuestion")) | length' 2>/dev/null)
if [ -n "$ASK_COUNT" ] && [ "$ASK_COUNT" != "0" ]; then
  exit 0
fi

# Keyword patterns sourced from data/hangul-patterns.regex
#   HG_BYPASS_KEYWORD_PATTERN     — delegation / next-step framing
#   HG_BYPASS_INTERROGATIVE_PATTERN — direct action-offer interrogative
# When the data file is absent both fall back to __NEVER_MATCH__ so the hook
# becomes a no-op (intentional — bypass framing is locale-specific).

if echo "$LAST_TEXT" | grep -qE "$HG_BYPASS_INTERROGATIVE_PATTERN"; then
  # Direct interrogative offer — fire regardless of list count.
  :
elif echo "$LAST_TEXT" | grep -qE "$HG_BYPASS_KEYWORD_PATTERN"; then
  # Delegation/next-step framing — require bullet/numbered list >= 2 (cuts FP).
  LIST_COUNT=$(echo "$LAST_TEXT" | grep -cE '^[[:space:]]*([0-9]+\.|[-*])[[:space:]]+')
  if [ "$LIST_COUNT" -lt 2 ]; then
    exit 0
  fi
else
  exit 0
fi

REMINDER="[hook:check-ask-bypass-keywords] Text-question pattern detected (delegation/next-step framing + list>=2, or direct interrogative offer) + no AskUserQuestion call in the same response.

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
