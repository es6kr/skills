#!/bin/bash
# next-reactive-guard.sh — UserPromptSubmit hook for the next skill.
#
# Reactive counterpart to next-trigger.sh (Stop hook). next-trigger.sh cannot
# fire on a continuation chain: once it blocks (decision:"block"), the resumed
# turn carries stop_hook_active=true and the hook MUST exit 0 or it would loop
# forever. Every "next call missed" recurrence (see failed-attempts.md
# "next-invocation") happens inside that suppressed window. No Stop-based guard
# can close it — but UserPromptSubmit fires on the NEXT prompt and CAN look back.
#
# On each user prompt, this guard inspects the PRIOR turn and injects a
# corrective reminder when ALL of:
#   1. Suppression — the latest next-trigger.debug.log entry for this transcript
#      is `suppressed=stop_hook_active` (the prior turn's Stop was silenced).
#   2. Completion — the prior turn's assistant text matches the completion
#      PATTERN (reused verbatim from next-trigger.sh's data/*.regex loader).
#   3. No next-after-completion — the last Skill("next") call in the prior turn
#      comes BEFORE the last completion signal (a mid-turn next ask does NOT
#      satisfy a later batch completion — suggestion-patterns row 7). Firing on
#      "completion with no subsequent next" catches the exact "already-invoked-
#      this-chain" rationalization variant, not just "next never called".
#   4. No terminal ask — the completion signal is also NOT followed by an
#      AskUserQuestion. A turn that ends on an ask (e.g. /wip Step 2 per-item
#      direction, /fix disposition) surfaced follow-up to the user directly, so
#      an earlier completion signal is not an un-followed batch. Without this,
#      the guard false-fired on every ask-terminal turn (the known FP).
#
# Reactive limitation: fires on the NEXT prompt, so it cannot prevent the
# same-turn miss — it offloads detection from the user to the hook.
#
# Responsibility: next skill (automation.md). Registered directly from
# resources/ (like next-trigger.sh) so ../data and the debug log resolve.
# Input (stdin): JSON { transcript_path, ... }
# Output (stdout): on fire, {"hookSpecificOutput":{"hookEventName":
#   "UserPromptSubmit","additionalContext":"<reminder>"}}. Otherwise empty.

set -euo pipefail

INPUT="$(cat)"
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // ""' 2>/dev/null || echo "")
[[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]] && exit 0

SELFDIR="$(cd "$(dirname "$0")" && pwd)"
GUARD_LOG="$SELFDIR/next-reactive-guard.debug.log"

# --- Signal 1: continuation-chain suppression -------------------------------
# The debug log lives next to next-trigger.sh (same resources/ dir). Resolve it
# tolerantly in case this guard is run from a copied location.
# NEXT_TRIGGER_DEBUG_LOG overrides for testing (fixture harness drives it).
DEBUG_LOG="${NEXT_TRIGGER_DEBUG_LOG:-}"
if [[ -z "$DEBUG_LOG" ]]; then
  for cand in "$SELFDIR/next-trigger.debug.log" \
              "$HOME/.agents/skills/next/resources/next-trigger.debug.log" \
              "$HOME/.claude/skills/next/resources/next-trigger.debug.log"; do
    [[ -f "$cand" ]] && { DEBUG_LOG="$cand"; break; }
  done
fi
[[ -z "$DEBUG_LOG" || ! -f "$DEBUG_LOG" ]] && exit 0

# Latest next-trigger entry for THIS transcript must be a stop_hook_active
# suppression — i.e. the prior turn's Stop hook was silenced (the blind spot).
LATEST=$(grep -F "transcript=$TRANSCRIPT" "$DEBUG_LOG" 2>/dev/null | tail -1 || true)
[[ "$LATEST" != *"suppressed=stop_hook_active"* ]] && exit 0

# --- Completion PATTERN (reused from next-trigger.sh) -----------------------
DATA_DIR="$SELFDIR/../data"
if compgen -G "$DATA_DIR/*.regex" > /dev/null 2>&1; then
  PATTERN=$(cat "$DATA_DIR"/*.regex | sed 's/#.*$//' | awk 'NF' | paste -sd'|' -)
else
  PATTERN='Fix complete:|✅|all done|^[[:space:]]*done\.|task (complete|completed|finished)|completed[\.\!\)\*,[:space:]]|finished[\.\!\)\*,[:space:]]|wrapped up'
fi

# --- Signals 2 & 3: ordered completion-vs-next events over the prior turn ----
# Emit, in transcript order, one token per relevant event since the last real
# user prompt (a user message whose content is a STRING — tool_result content
# is an array, so those anchor lines are skipped, mirroring next-trigger.sh):
#   "N"        -> a Skill("next") tool_use
#   "A"        -> an AskUserQuestion tool_use (terminal ask suppresses firing)
#   "T\t<txt>" -> an assistant text block (tested against PATTERN below)
STREAM=$(jq -R 'fromjson? // empty' "$TRANSCRIPT" 2>/dev/null | jq -rs '
  [ .[] | select(type == "object") ] as $e
  | if ($e | length) == 0 then empty
    else
      ([ range(0; ($e | length))
         | select($e[.].type == "user" and (($e[.].message.content? | type) == "string")) ] | max // -1) as $lu
      | $e[($lu + 1):][]
      | select(.type == "assistant")
      | (.message.content // [])[]
      | if .type == "text" then "T\t" + ((.text // "") | gsub("\n"; " "))
        elif (.type == "tool_use" and .name == "Skill" and ((.input.skill? // "") == "next")) then "N"
        elif (.type == "tool_use" and .name == "AskUserQuestion") then "A"
        else empty end
    end
' 2>/dev/null || echo "")

last_c=-1   # index of last completion-signal text block
last_n=-1   # index of last Skill("next") call
last_a=-1   # index of last AskUserQuestion tool_use
idx=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  idx=$((idx + 1))
  if [[ "$line" == "N" ]]; then
    last_n=$idx
  elif [[ "$line" == "A" ]]; then
    last_a=$idx
  else
    txt=${line#T$'\t'}
    if printf '%s' "$txt" | grep -qiE "$PATTERN"; then
      last_c=$idx
    fi
  fi
done <<< "$STREAM"

# Diagnostics (matches next-trigger.sh's evidence-trail philosophy).
{
  printf '%s\ttranscript=%s\tlast_c=%s\tlast_n=%s\tlast_a=%s\tfire=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$TRANSCRIPT" "$last_c" "$last_n" "$last_a" \
    "$([[ "$last_c" -gt "$last_n" && "$last_c" -gt "$last_a" ]] && echo true || echo false)" >> "$GUARD_LOG"
  if [[ "$(wc -l < "$GUARD_LOG" 2>/dev/null || echo 0)" -gt 500 ]]; then
    tail -n 200 "$GUARD_LOG" > "$GUARD_LOG.tmp" && mv "$GUARD_LOG.tmp" "$GUARD_LOG"
  fi
} 2>/dev/null || true

# Fire when a completion signal is the last relevant event — no Skill("next")
# AND no AskUserQuestion after it (last_n/last_a == -1 means never called this
# turn). A terminal ask surfaced follow-up directly, so it suppresses firing.
if [[ "$last_c" -gt "$last_n" && "$last_c" -gt "$last_a" ]]; then
  REASON='next-invocation continuation-chain guard: the prior turn appears to have completed a task batch inside the stop_hook_active window (Stop hook suppressed) without a Skill("next") call after the completion. A mid-turn ask does not satisfy a batch-completion next-action ask (suggestion-patterns row 7). If a batch actually completed, invoke the `next` skill now to surface follow-up options before continuing; if not, proceed.'
  jq -cn --arg ctx "$REASON" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
fi

exit 0
