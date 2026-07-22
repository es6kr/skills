#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block session wrap-up/cleanup options below the
# context-usage gate threshold.
#
# Trigger: an AskUserQuestion option proposes session wrap-up ("wrap-up",
#          "wrap up", "/cleanup", "session cleanup") while the live context
#          usage (recomputed on demand from the transcript) is < 45%.
# Action: Deny with guidance — drop the option, or mark it "user-requested"
#         when the user explicitly asked to wrap up.
#
# Background: the next skill's "Context-usage gate" permits a wrap-up option
# only on explicit user signal OR context usage >= 45%. The injected signal
# refreshes only on user-prompt events (and a compact shrinks context), so a
# reading cached from an earlier prompt is stale — which is why this hook
# recomputes a LIVE figure on demand rather than trusting the injected line.
# It enforces the deterministic half of the gate (threshold vs live figure);
# the user-signal half is handled by the composer via the "user-requested"
# marker. Recurrence family tracked in failed-attempts.md
# (grep "context-usage").

# Fallback only. The live per-model value (fable/mythos 55, opus 50, others 45)
# is published by context-usage-inject.sh and overrides this below; 45 is the
# floor used when that script is unavailable.
THRESHOLD=45

# Korean wrap-up keyword overlay (git-ignored in the PUBLIC repo — see
# hook-kit/data/hangul-patterns.regex header). Falls back to English-only
# detection when the data file is absent (published/local-no-data installs).
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  . "$HG_DATA_FILE"
fi
WRAPUP_PATTERN_EN='wrap[- ]?up|/cleanup|session cleanup|retrospect'
if [[ -n "${HG_CONTEXT_GATE_WRAPUP_KO:-}" ]]; then
  WRAPUP_PATTERN="${WRAPUP_PATTERN_EN}|${HG_CONTEXT_GATE_WRAPUP_KO}"
else
  WRAPUP_PATTERN="$WRAPUP_PATTERN_EN"
fi

# End/stop option = deterministic signal that the ask IS a session wrap-up ask
# (the composer offered an explicit "end/stop the session" choice). Used by the
# UNDER-offer check below: a wrap-up ask that omits the cleanup option at >=
# threshold is the mirror failure (context-usage gate positive trigger).
ENDSTOP_PATTERN_EN='stop here|end session|end the session|end this session'
if [[ -n "${HG_CONTEXT_GATE_ENDSTOP_KO:-}" ]]; then
  ENDSTOP_PATTERN="${ENDSTOP_PATTERN_EN}|${HG_CONTEXT_GATE_ENDSTOP_KO}"
else
  ENDSTOP_PATTERN="$ENDSTOP_PATTERN_EN"
fi

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "AskUserQuestion" ]]; then
  exit 0
fi

# Detection is scoped to OPTION label/description only — an OFFER lives in the
# options. Question text merely mentioning the gate or a withdrawn cleanup
# option ("the cleanup option is withdrawn because ...") must not match.
OPT_TEXTS=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? | .options[]? |
  (.label // ""), (.description // "")
' 2>/dev/null)

# Check if any wrap-up or end/stop option is marked user-requested
ANY_USER_REQUESTED_WRAPUP=$(echo "$INPUT" | jq --arg wrap "$WRAPUP_PATTERN" --arg end "$ENDSTOP_PATTERN" -r '
  [
    .tool_input.questions[]? | .options[]? |
    select((.label // "") + " " + (.description // "") | test($wrap + "|" + $end; "i")) |
    select((.label // "") + " " + (.description // "") | test("user.?requested"; "i"))
  ] | length
' 2>/dev/null)

if [[ "$ANY_USER_REQUESTED_WRAPUP" -gt 0 ]]; then
  exit 0
fi

# Scoped detection of cleanup and end/stop options
HAS_CLEANUP=$(echo "$INPUT" | jq --arg pattern "$WRAPUP_PATTERN" -r '
  [
    .tool_input.questions[]? | .options[]? |
    select((.label // "") + " " + (.description // "") | test($pattern; "i"))
  ] | length
' 2>/dev/null)

HAS_ENDSTOP=$(echo "$INPUT" | jq --arg pattern "$ENDSTOP_PATTERN" -r '
  [
    .tool_input.questions[]? | .options[]? |
    select((.label // "") + " " + (.description // "") | test($pattern; "i"))
  ] | length
' 2>/dev/null)

# Neither an offered cleanup option nor an end/stop wrap-up signal → not a
# wrap-up ask in either direction. Nothing to judge.
if [[ "$HAS_CLEANUP" == "0" && "$HAS_ENDSTOP" == "0" ]]; then
  exit 0
fi

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  exit 0
fi

# LIVE reading — NOT the injected `Context usage:` line. That injected figure
# only refreshes on UserPromptSubmit, so during a long single assistant turn
# (many tool calls, no intervening user prompt) it freezes at an early-turn
# value; both the over- and under-offer checks then misfire (the exact 2nd
# recurrence this guard was defeated by). Recompute the live figure on demand
# from the transcript's last assistant-message usage field via the sibling
# context-usage-inject.sh (the same source the injection hook uses).
CTX_INJECT="$(dirname "$0")/context-usage-inject.sh"
LATEST_PCT=""
if [[ -f "$CTX_INJECT" ]]; then
  # One invocation yields both figures. CC_EMIT_THRESHOLD makes the script
  # publish the per-model threshold it would apply, so this guard and the
  # injected recommendation can never disagree about where the line sits.
  # Backslashes must be escaped before embedding in JSON: a Windows transcript
  # path (C:\Users\...) otherwise produces invalid JSON, the parse fails, and
  # this guard silently degrades to "no signal" on every call.
  TRANSCRIPT_JSON=${TRANSCRIPT//\\/\\\\}
  CTX_OUT=$(printf '{"transcript_path": "%s"}' "$TRANSCRIPT_JSON" \
    | CC_EMIT_THRESHOLD=1 bash "$CTX_INJECT" 2>/dev/null)
  LATEST_PCT=$(printf '%s' "$CTX_OUT" \
    | grep -o 'Context usage: ~[0-9.]*k / [0-9]*k tokens ([0-9.]*%)' \
    | tail -1 | grep -o '([0-9.]*%)' | tr -d '(%)')
  LIVE_THRESHOLD=$(printf '%s' "$CTX_OUT" \
    | grep -o 'CLEANUP-THRESHOLD: [0-9]*' | tail -1 | grep -o '[0-9]*')
  [[ -n "$LIVE_THRESHOLD" ]] && THRESHOLD="$LIVE_THRESHOLD"
fi
if [[ -z "$LATEST_PCT" ]]; then
  # Live script absent/failed — fall back to the latest injected attachment
  # figure (stale-prone, but better than no signal). Structure-anchored to
  # type:"attachment" entries so assistant/tool echoes don't contaminate it.
  LATEST_PCT=$(cat "$TRANSCRIPT" 2>/dev/null \
    | jq -Rr 'fromjson? | select(.type=="attachment") | .attachment.content // empty' 2>/dev/null \
    | grep -o 'Context usage: ~[0-9.]*k / [0-9]*k tokens ([0-9.]*%)' \
    | tail -1 | grep -o '([0-9.]*%)' | tr -d '(%)')
fi
if [[ -z "$LATEST_PCT" ]]; then
  # No signal at all — the deterministic half cannot be judged; leave the
  # decision to the composer (conservative: no false block).
  exit 0
fi

BELOW=$(awk -v p="$LATEST_PCT" -v t="$THRESHOLD" 'BEGIN { print (p < t) ? 1 : 0 }')

# OVER-offer: cleanup option present while BELOW threshold (premature wrap-up).
if [[ "$HAS_CLEANUP" == "1" && "$BELOW" == "1" ]]; then
  {
    echo "DENIED: AskUserQuestion offers a session wrap-up/cleanup option below the context-usage gate."
    echo ""
    echo "Live context usage: ${LATEST_PCT}% (< ${THRESHOLD}% threshold)."
    echo ""
    echo "Why blocked:"
    echo "  - The next skill's Context-usage gate permits a wrap-up option only on"
    echo "    explicit user signal OR latest injected usage >= ${THRESHOLD}%"
    echo "  - The signal refreshes only on user-prompt events; a figure cached from an"
    echo "    earlier prompt (especially across a compact boundary) overstates usage"
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Drop the wrap-up/cleanup option — fill the slot with another candidate"
    echo "  2. If the user explicitly asked to wrap up, restate that in the option"
    echo "     description with the marker 'user-requested' (e.g. 'user-requested wrap-up')"
    echo ""
    echo "Reference: next skill suggestion-patterns.md 'Context-usage gate';"
    echo "  failed-attempts.md (grep \"context-usage\")"
  } >&2
  exit 2
fi

# UNDER-offer (positive-trigger enforcement): the ask IS a wrap-up ask (an
# end/stop option is present) and context is AT/ABOVE threshold, but NO cleanup/
# retrospective option was offered. Omitting cleanup at a full session is the
# mirror failure the gate's positive trigger forbids.
if [[ "$HAS_ENDSTOP" == "1" && "$HAS_CLEANUP" == "0" && "$BELOW" == "0" ]]; then
  {
    echo "DENIED: session wrap-up ask at >= ${THRESHOLD}% context omits the cleanup/retrospective option."
    echo ""
    echo "Live context usage: ${LATEST_PCT}% (>= ${THRESHOLD}% threshold)."
    echo "The options include an end/stop-session choice but no cleanup/retrospective option."
    echo ""
    echo "Why blocked:"
    echo "  - The Context-usage gate's positive trigger: at/above ${THRESHOLD}% in a"
    echo "    wrapping-up context, the cleanup/retrospective option is REQUIRED, not optional"
    echo "  - 'End/Stop session' is NOT a substitute — it ends without the retrospect/"
    echo "    persist/prune value. The user's correction: at >=${THRESHOLD}%, ask whether to cleanup"
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Add a cleanup/retrospective option (or an explicit 'run cleanup now vs defer' choice)"
    echo "  2. If the user already declined cleanup this session, mark an option 'user-requested'"
    echo "     (e.g. 'user-requested stop, cleanup declined')"
    echo ""
    echo "Reference: next skill suggestion-patterns.md 'Context-usage gate' positive trigger;"
    echo "  failed-attempts.md (grep \"context-usage\")"
  } >&2
  exit 2
fi

exit 0
