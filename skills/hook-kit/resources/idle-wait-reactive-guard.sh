#!/bin/bash
# idle-wait-reactive-guard.sh — UserPromptSubmit hook, reactive companion to
# block-idle-wait-without-short-cycle.sh (Stop hook).
#
# Same structural gap as next-reactive-guard.sh / next-trigger.sh: a Stop hook
# cannot fire on every ending within a continuation chain. Once it blocks
# (decision:"block") once, the resumed turn carries stop_hook_active=true, and
# any LATER Stop event in that same suppressed window is silently ignored by
# the harness. block-idle-wait-without-short-cycle.sh caught the FIRST silent-
# wait ending in a chain but missed a second, identical ending immediately
# after — no Stop-based guard can close that window. UserPromptSubmit fires on
# the NEXT real user prompt and CAN look back at the turn that just ended.
#
# Detection reuses the exact 3-condition contract from
# block-idle-wait-without-short-cycle.sh, applied to the PRIOR turn (the one
# that just silently ended, right before this new prompt was submitted):
#   1. Background dispatch marker present in the prior turn's raw transcript
#      text (same literal strings the Stop hook matches).
#   2. Prior turn's LAST assistant text block matches the waiting-phrase
#      pattern (same locale-data-driven pattern the Stop hook uses).
#   3. No "[idle-ok]" annotation in that text.
#
# Output: additionalContext reminder only — UserPromptSubmit cannot block a
# turn that already ended; it can only inform the NEXT turn.
#
# Responsibility: hook-kit (this hook has no dedicated domain skill; idle-wait
# discipline is a general session-lifecycle concern, so it defaults here per
# the hook-ownership policy's "no domain skill -> hook-kit is the default
# installer" rule).
#
# Input (stdin): JSON { transcript_path, ... }
# Output (stdout): on fire, {"hookSpecificOutput":{"hookEventName":
#   "UserPromptSubmit","additionalContext":"<reminder>"}}. Otherwise empty.

set -euo pipefail

[[ "${RALPH_LOOP:-}" == "1" ]] && exit 0

INPUT="$(cat)"
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null || echo "")
[[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]] && exit 0

SELFDIR="$(cd "$(dirname "$0")" && pwd)"
HG_DATA_FILE="$SELFDIR/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then . "$HG_DATA_FILE"; fi
WAIT_PHRASES="${HG_IDLE_WAIT_PHRASES:-(wait(ing)? (for|on)|will (resume|continue) (when|once)|resume once|until (it|they) complete)}"

# Isolate the prior turn: raw JSONL lines between the second-to-last real user
# prompt (string content — an actual typed message, not a tool_result array)
# and the most recent one. That range is exactly the turn that just silently
# ended before this new prompt was submitted.
PRIOR_TURN_RAW=$(jq -R 'fromjson? // empty' "$TRANSCRIPT" 2>/dev/null | jq -rs '
  [ .[] | select(type == "object") ] as $e
  | if ($e | length) == 0 then empty
    else
      ([ range(0; ($e | length))
         | select($e[.].type == "user" and (($e[.].message.content? | type) == "string")) ]) as $user_idxs
      | ($user_idxs[-2]? // -1) as $start
      | ($user_idxs[-1]? // ($e | length)) as $end
      | $e[($start + 1):$end][]
      | tojson
    end
' 2>/dev/null || echo "")
[[ -z "$PRIOR_TURN_RAW" ]] && exit 0

# Condition 1: background dispatch marker anywhere in the prior turn's raw text.
if ! printf '%s' "$PRIOR_TURN_RAW" | grep -qE 'Command running in background with ID:|Async agent launched successfully|The agent is (now running|working in the background)'; then
  exit 0
fi

# Last assistant text block within that same range.
LAST_TEXT=$(printf '%s' "$PRIOR_TURN_RAW" | jq -rs '
  [ .[] | select(type=="object" and .type=="assistant")
    | (.message.content
       | if type == "array" then ([.[] | select(.type? == "text") | .text] | join(" "))
         elif type == "string" then . else "" end)
    | select(length > 0)
  ] | last // "" | .[-300:]
' 2>/dev/null)
[[ -z "$LAST_TEXT" ]] && exit 0

# Condition 3: explicit idle-ok annotation exempts.
if printf '%s' "$LAST_TEXT" | grep -qF '[idle-ok]'; then
  exit 0
fi

# Condition 2: waiting-posture close?
if ! printf '%s' "$LAST_TEXT" | grep -qiE "$WAIT_PHRASES"; then
  exit 0
fi

REASON='idle-wait continuation-chain guard: the PRIOR turn ended in a silent-wait posture (background work dispatched, final text closed on a waiting phrase, no [idle-ok] marker) — block-idle-wait-without-short-cycle.sh (Stop hook) cannot fire on every ending within a stop_hook_active-suppressed chain, only the first. If background work is still in flight and nothing is drivable, either drive a deferred item now, re-arm a short (<=240s) wakeup cycle, or state the judgment explicitly and append [idle-ok]. Do not repeat a bare waiting close.'
jq -cn --arg ctx "$REASON" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
exit 0
