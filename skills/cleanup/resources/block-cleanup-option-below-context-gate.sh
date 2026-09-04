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
#
# Under-offer scope (2026-08-03 widened, class
# context-gate-cleanup-not-marked-recommended 2nd occurrence): the positive-
# trigger check originally required an explicit end/stop-session OPTION to
# even consider an ask "wrap-up-scoped" — an ask that doesn't yet frame itself
# that way (e.g. a plain "decide X" ask mid-work, no end/stop option) bypassed
# the gate entirely regardless of live usage. The QUESTION TEXT is now also
# checked for "next action" framing (the next skill's own canonical phrasing,
# "what would you like to do next?") — either signal now scopes the ask in.

# Fallback only. The live per-model value (fable/mythos 55, opus 50, others 45)
# is published by context-usage-inject.sh and overrides this below; 45 is the
# floor used when that script is unavailable.
THRESHOLD=45

# Korean wrap-up keyword overlay (git-ignored in the PUBLIC repo — see
# hook-kit/data/hangul-patterns.regex header). Falls back to English-only
# detection when the data file is absent (published/local-no-data installs).
HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  . "$HG_DATA_FILE"
fi
# Negative lookbehind on "/cleanup" excludes a bare substring match inside
# unrelated slash-delimited text (e.g. "resume/shutdown/cleanup/agent-messages")
# — only a standalone "/cleanup" token (not preceded by alnum or another slash)
# counts as the slash-command reference.
WRAPUP_PATTERN_EN='wrap[- ]?up|(?<![a-zA-Z0-9/])/cleanup|session cleanup|retrospect'
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

# "Next action" QUESTION-TEXT framing = second deterministic signal that the
# ask IS wrap-up-scoped, independent of whether an end/stop OPTION was
# offered. Matches the next skill's own canonical question ("What would you
# like to do next?") and close variants. Scoped to the question text, not
# options — see OPT_TEXTS comment below for why options-only scoping exists
# for the cleanup/end-stop patterns.
NEXTACTION_PATTERN_EN='what would you like to do next|what.?s next\??|what next\??'
if [[ -n "${HG_CONTEXT_GATE_NEXTACTION_KO:-}" ]]; then
  NEXTACTION_PATTERN="${NEXTACTION_PATTERN_EN}|${HG_CONTEXT_GATE_NEXTACTION_KO}"
else
  NEXTACTION_PATTERN="$NEXTACTION_PATTERN_EN"
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

# "Next action" framing lives in the QUESTION text, not the options (that's
# where the composer states the ask's purpose — e.g. "What would you like to
# do next?"). A second, independent wrap-up-scoping signal from HAS_ENDSTOP.
HAS_NEXTACTION=$(echo "$INPUT" | jq --arg pattern "$NEXTACTION_PATTERN" -r '
  [
    .tool_input.questions[]? | (.question // "") |
    select(test($pattern; "i"))
  ] | length
' 2>/dev/null)

# Neither an offered cleanup option, nor an end/stop wrap-up option, nor
# next-action question-text framing → not a wrap-up ask in any direction.
# Nothing to judge.
if [[ "$HAS_CLEANUP" == "0" && "$HAS_ENDSTOP" == "0" && "$HAS_NEXTACTION" == "0" ]]; then
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
# from the transcript's last assistant-message usage field via
# context-usage-inject.sh (the same source the injection hook uses).
#
# This script now lives in cleanup/resources/ (moved out of hook-kit, which
# still owns context-usage-inject.sh itself), so it is no longer a
# same-directory sibling — probe a path chain instead of hardcoding one path.
# A single hardcoded path silently degrades this guard to "no signal"
# wherever it does not resolve, and the failure is invisible: LATEST_PCT
# stays empty and the guard falls back to the STALE injected figure, which is
# exactly the bug this LIVE reading exists to avoid. Observed 2026-08-16: two
# installed copies of this guard returned 62.8% and 24.0% for the same ask,
# purely because one resolved its path and the other did not.
#   1. hook-kit sibling resource   — current real location (this repo)
#   2. context-measure skill       — anticipated future split-out location
#   3. ${CLAUDE_PLUGIN_ROOT}       — plugin-relative, set when run as a plugin hook
#   4. $HOME/.claude/skills/...    — legacy absolute path, kept for back-compat
CTX_INJECT=""
for _cand in \
  "$(dirname "$0")/../../session/resources/context-usage-inject.sh" \
  "$(dirname "$0")/../../hook-kit/resources/context-usage-inject.sh" \
  "$(dirname "$0")/../../context-measure/resources/context-usage-inject.sh" \
  "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/session/resources/context-usage-inject.sh" \
  "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/hook-kit/resources/context-usage-inject.sh" \
  "$HOME/.claude/skills/session/resources/context-usage-inject.sh" \
  "$HOME/.claude/skills/hook-kit/resources/context-usage-inject.sh"; do
  if [[ -f "$_cand" ]]; then CTX_INJECT="$_cand"; break; fi
done
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

# MISSING-CITATION (3rd check, restored — class context-usage-stale, was documented as
# added at the 13th occurrence but the deployed file never carried it; re-added after a
# 17th-occurrence catch confirmed the gap): a legitimate cleanup offer (HAS_CLEANUP==1,
# not already denied above as OVER-offer, i.e. BELOW==0) whose option text substitutes
# qualitative language ("session grew large") for the actual live percentage. A number
# must appear in the SAME option's label+description — citing a number anywhere else in
# the ask (e.g. the question text) does not satisfy this.
CLEANUP_OPT_TEXT=$(echo "$INPUT" | jq --arg pattern "$WRAPUP_PATTERN" -r '
  [
    .tool_input.questions[]? | .options[]? |
    select((.label // "") + " " + (.description // "") | test($pattern; "i")) |
    (.label // "") + " " + (.description // "")
  ] | join(" ")
' 2>/dev/null)

if [[ "$HAS_CLEANUP" == "1" && "$BELOW" == "0" ]]; then
  if ! echo "$CLEANUP_OPT_TEXT" | grep -qE '[0-9]+(\.[0-9]+)?[[:space:]]*%'; then
    {
      echo "DENIED: cleanup/wrap-up option omits the live numeric context-usage percentage."
      echo ""
      echo "Live context usage: ${LATEST_PCT}% (>= ${THRESHOLD}% threshold — the offer itself is legitimate)."
      echo ""
      echo "Why blocked:"
      echo "  - The offered option's label+description contains no [0-9]+% figure — qualitative"
      echo "    phrasing ('session grew large', 'context is high') is not a substitute for the"
      echo "    cited number the user needs to judge the recommendation"
      echo ""
      echo "Required action:"
      echo "  Restate the option description to cite the live figure, e.g."
      echo "  \"Context usage: ~${LATEST_PCT}% — session cleanup and retrospective\""
      echo ""
      echo "Reference: next skill suggestion-patterns.md 'Context-usage gate' Don't/Do #5;"
      echo "  failed-attempts.md class context-usage-stale (13th occurrence)"
    } >&2
    exit 2
  fi
fi

# UNDER-offer (positive-trigger enforcement): the ask IS wrap-up-scoped
# (either an end/stop option is present, OR the question text uses
# "next action" framing like "what would you like to do next?") and context
# is AT/ABOVE threshold, but NO cleanup/retrospective option was offered.
# Omitting cleanup at a full session is the mirror failure the gate's
# positive trigger forbids — widened 2026-08-03 so a plain next-action ask
# (no end/stop option yet) is caught too, not just asks that already frame
# themselves as ending the session.
if [[ ( "$HAS_ENDSTOP" == "1" || "$HAS_NEXTACTION" == "1" ) && "$HAS_CLEANUP" == "0" && "$BELOW" == "0" ]]; then
  {
    echo "DENIED: wrap-up-scoped ask at >= ${THRESHOLD}% context omits the cleanup/retrospective option."
    echo ""
    echo "Live context usage: ${LATEST_PCT}% (>= ${THRESHOLD}% threshold)."
    echo "Signal: $( [[ "$HAS_ENDSTOP" == "1" ]] && echo -n "an end/stop-session option is present" )$( [[ "$HAS_ENDSTOP" == "1" && "$HAS_NEXTACTION" == "1" ]] && echo -n " and " )$( [[ "$HAS_NEXTACTION" == "1" ]] && echo -n "the question text uses next-action framing" ) — but no cleanup/retrospective option was offered."
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

# GENERIC-CITATION (5th check, new -- closes the gap where an end/stop-framed
# ask never offers a cleanup-labeled option at all (below threshold, or the
# composer chose a plain "continue vs stop" framing instead) and therefore
# skips every check above untouched -- all of them require a cleanup option
# to be present or the reading to already be at/above threshold before they
# even look at citation. The point of citing % is to let the user judge for
# themselves regardless of which side of the cleanup threshold the ask lands
# on, so this check fires whenever the ask carries end/stop framing
# (HAS_ENDSTOP==1) and NO number appears anywhere in the ask (question text
# or any option text), independent of HAS_CLEANUP/BELOW.
ALL_ASK_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.question // ""), (.options[]? | (.label // "") + " " + (.description // ""))
' 2>/dev/null)

if [[ "$HAS_ENDSTOP" == "1" ]] && ! echo "$ALL_ASK_TEXT" | grep -qE '[0-9]+(\.[0-9]+)?[[:space:]]*%'; then
  {
    echo "DENIED: end/stop-session ask cites no live context-usage percentage anywhere."
    echo ""
    echo "Live context usage: ${LATEST_PCT}% (threshold ${THRESHOLD}% -- informational here, not the gate)."
    echo ""
    echo "Why blocked:"
    echo "  - A plain 'continue vs stop' ask with end/stop framing but no cleanup-labeled"
    echo "    option falls outside the OVER/MISSING-CITATION/UNDER-offer checks above,"
    echo "    which all require a cleanup option or an at/above-threshold reading first"
    echo "  - The user needs the number to judge for themselves whether to keep going,"
    echo "    independent of whether this ask crosses the cleanup-recommendation threshold"
    echo ""
    echo "Required action:"
    echo "  Cite the live figure in the question text or an option, e.g."
    echo "  \"... (context usage: ~${LATEST_PCT}%) ...\""
    echo ""
    echo "Reference: failed-attempts.md class context-usage-stale (19th occurrence)"
  } >&2
  exit 2
fi

exit 0
