#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — Block session wrap-up/cleanup options below the
# context-usage gate threshold.
#
# Trigger: an AskUserQuestion option proposes session wrap-up ("wrap-up",
#          "wrap up", "/cleanup", "session cleanup") while the transcript's
#          LATEST injected `Context usage: ... (NN.N%)` line reports < 45%.
# Action: Deny with guidance — drop the option, or mark it "user-requested"
#         when the user explicitly asked to wrap up.
#
# Background: the next skill's "Context-usage gate" permits a wrap-up option
# only on explicit user signal OR latest injected usage >= 45%. The signal
# refreshes only on user-prompt events and a compact boundary shrinks context,
# so a reading cached from an earlier prompt overstates usage. This hook
# enforces the deterministic half of the gate (threshold vs transcript-latest
# figure); the user-signal half is handled by the composer via the
# "user-requested" marker. Recurrence family tracked in failed-attempts.md
# (grep "context-usage").

THRESHOLD=45

# Korean wrap-up keyword overlay (git-ignored in the PUBLIC repo — see
# hook-kit/data/hangul-patterns.regex header). Falls back to English-only
# detection when the data file is absent (published/local-no-data installs).
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  . "$HG_DATA_FILE"
fi
WRAPUP_PATTERN_EN='wrap[- ]?up|/cleanup|session cleanup'
if [[ -n "${HG_CONTEXT_GATE_WRAPUP_KO:-}" ]]; then
  WRAPUP_PATTERN="${WRAPUP_PATTERN_EN}|${HG_CONTEXT_GATE_WRAPUP_KO}"
else
  WRAPUP_PATTERN="$WRAPUP_PATTERN_EN"
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

# Wrap-up option detection — narrow patterns only ("cleanup orphan agents",
# "docker cleanup" etc. must NOT match; require wrap-up wording, the /cleanup
# slash command, explicit "session cleanup", or (when the data overlay is
# present) the locale-specific session-wrap-up equivalents defined in
# hangul-patterns.regex (HG_CONTEXT_GATE_WRAPUP_KO).
if ! echo "$OPT_TEXTS" | grep -qiE "$WRAPUP_PATTERN"; then
  exit 0
fi

# Composer marked the option as explicitly user-requested → gate condition 1.
if echo "$OPT_TEXTS" | grep -qiE 'user.?requested'; then
  exit 0
fi

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  exit 0
fi

# Latest injected figure wins — earlier readings are stale by definition.
# Structure-anchored: only type:"attachment" entries carry genuine hook
# injections. Assistant text / tool-command echoes quoting the same pattern
# live in other entry types and must not contaminate the reading.
LATEST_PCT=$(grep '"type":"attachment"' "$TRANSCRIPT" 2>/dev/null \
  | jq -Rr 'fromjson? | select(.type=="attachment") | .attachment.content // empty' 2>/dev/null \
  | grep -o 'Context usage: ~[0-9.]*k / [0-9]*k tokens ([0-9.]*%)' \
  | tail -1 | grep -o '([0-9.]*%)' | tr -d '(%)')
if [[ -z "$LATEST_PCT" ]]; then
  # No injected signal in this environment — the deterministic half cannot be
  # judged; leave the decision to the composer (conservative: no false block).
  exit 0
fi

BELOW=$(awk -v p="$LATEST_PCT" -v t="$THRESHOLD" 'BEGIN { print (p < t) ? 1 : 0 }')
if [[ "$BELOW" != "1" ]]; then
  exit 0
fi

{
  echo "DENIED: AskUserQuestion offers a session wrap-up/cleanup option below the context-usage gate."
  echo ""
  echo "Latest injected context usage: ${LATEST_PCT}% (< ${THRESHOLD}% threshold)."
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
