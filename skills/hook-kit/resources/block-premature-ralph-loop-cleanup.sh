#!/usr/bin/env bash
# PreToolUse:Skill — Block a direct Skill("cleanup", ...) call made while an
# active ralph-loop's live context usage is still below its own completion
# threshold.
#
# Trigger: tool_name == "Skill", tool_input.skill (or .name) == "cleanup",
#          AND a ralph-loop state file in the current workspace shows
#          active: true, AND live context usage (recomputed on demand) is
#          below the loop's own completion-promise threshold (parsed from
#          the state file's completion_promise field, falling back to the
#          standard 45%/per-model floor).
# Action: Deny — cleanup is a session-wrap-up procedure; the self-paced loop
#         invariant is "default action = CONTINUE the work", not "finish the
#         stated task list, then immediately wrap up regardless of the
#         threshold". Continue substantive work instead.
#
# Background: `block-cleanup-option-below-context-gate.sh` already covers
# this SAME failure mode when it reaches the user via an AskUserQuestion
# option — but a self-paced/ralph-loop iteration typically calls
# `Skill("cleanup", ...)` DIRECTLY on its own literal reading of a re-fired
# prompt ("finish remaining tasks, then /cleanup"), never routing through
# AskUserQuestion at all. That path was completely uncovered.
#
# This is (at minimum) the 3rd+ occurrence of the broader "self-paced loop
# invokes a terminal/wrap-up action before its own threshold is genuinely
# reached" class — see failed-attempts.md archive entry "stale context
# reading after rewind misjudged as over-threshold, causing a self-paced
# loop to end prematurely and run cleanup" (2026-07-23, 5+ recurrences
# documented there) plus at least 2 further same-day-family recurrences on
# 2026-08-09/2026-08-10. Per the fix skill's
# escalation matrix (1st=rule, 2nd=hook review, 3rd+=hook required), a
# deterministic hook is now the correct tier — a rule/memory note alone has
# already been shown (repeatedly) not to hold under loop-reentry momentum.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Skill" ]]; then
  exit 0
fi

SKILL_NAME=$(echo "$INPUT" | jq -r '.tool_input.skill // .tool_input.name // empty' 2>/dev/null)
if [[ "$SKILL_NAME" != "cleanup" ]]; then
  exit 0
fi

# Locate an active ralph-loop state file. The plugin writes it under the cwd
# at invocation time as `.claude/ralph-loop.local.md`; search upward from the
# transcript's cwd hint plus common workspace roots rather than assuming a
# single fixed path.
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

STATE_FILE=""
for CANDIDATE in "$CWD/.claude/ralph-loop.local.md" "./.claude/ralph-loop.local.md"; do
  if [[ -n "$CANDIDATE" && -f "$CANDIDATE" ]]; then
    STATE_FILE="$CANDIDATE"
    break
  fi
done

if [[ -z "$STATE_FILE" ]]; then
  # No active ralph-loop state discoverable — this specific recurring failure
  # mode is scoped to self-paced loops. A normal (non-loop) direct cleanup
  # call is not what this hook guards against.
  exit 0
fi

ACTIVE=$(grep -m1 '^active:' "$STATE_FILE" 2>/dev/null | sed 's/^active:[[:space:]]*//')
if [[ "$ACTIVE" != "true" ]]; then
  exit 0
fi

# Threshold: parse a numeric percentage out of the state file's
# completion_promise field (e.g. "context usage > 45%" → 45, locale-
# agnostic — just extracts the first number). Fall back to the standard 45
# floor when no number is present (a non-numeric promise, e.g. "user says
# stop", cannot gate on context % at all — nothing to check).
PROMISE_LINE=$(grep -m1 '^completion_promise:' "$STATE_FILE" 2>/dev/null)
THRESHOLD=$(echo "$PROMISE_LINE" | grep -o '[0-9]\+' | head -1)
if [[ -z "$THRESHOLD" ]]; then
  exit 0
fi

if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  exit 0
fi

# context-usage-inject.sh lives in the context-measure skill (split out of
# hook-kit, 2026-08-10) — not a same-directory sibling, hence the explicit
# cross-skill path.
CTX_INJECT="$HOME/.claude/skills/context-measure/resources/context-usage-inject.sh"
LATEST_PCT=""
if [[ -f "$CTX_INJECT" ]]; then
  TRANSCRIPT_JSON=${TRANSCRIPT//\\/\\\\}
  CTX_OUT=$(printf '{"transcript_path": "%s"}' "$TRANSCRIPT_JSON" \
    | bash "$CTX_INJECT" 2>/dev/null)
  LATEST_PCT=$(printf '%s' "$CTX_OUT" \
    | grep -o 'Context usage: ~[0-9.]*k / [0-9]*k tokens ([0-9.]*%)' \
    | tail -1 | grep -o '([0-9.]*%)' | tr -d '(%)')
fi
if [[ -z "$LATEST_PCT" ]]; then
  # No live signal available — conservative: do not false-block.
  exit 0
fi

BELOW=$(awk -v p="$LATEST_PCT" -v t="$THRESHOLD" 'BEGIN { print (p < t) ? 1 : 0 }')

if [[ "$BELOW" == "1" ]]; then
  {
    echo "DENIED: Skill(\"cleanup\", ...) called directly while the active ralph-loop is below its own completion threshold."
    echo ""
    echo "Live context usage: ${LATEST_PCT}% (< ${THRESHOLD}% loop completion threshold, from ${STATE_FILE})."
    echo ""
    echo "Why blocked:"
    echo "  - cleanup is a session-WRAP-UP procedure (commit + self-improve + RAG store + wip)."
    echo "    Running it before the loop's own stop-condition is met contradicts the"
    echo "    'work-until-threshold loop invariant': default action = CONTINUE the work,"
    echo "    stop only at the explicit stop-condition."
    echo "  - This is a recurring failure class (5+ archived occurrences plus repeats on"
    echo "    2026-08-09/2026-08-10) — a re-fired loop prompt like 'finish remaining tasks,"
    echo "    then /cleanup' does NOT mean 'run cleanup the moment the stated task list is"
    echo "    empty' if context is still far below the threshold. It means cleanup is the"
    echo "    FINAL step, once the threshold is genuinely reached."
    echo ""
    echo "Required action (pick one before retrying):"
    echo "  1. Continue substantive work (more of the loop's stated task, or genuinely useful"
    echo "     follow-up work) until live usage reaches ${THRESHOLD}%, THEN call cleanup."
    echo "  2. If cleanup is genuinely warranted now for a reason unrelated to the loop's own"
    echo "     threshold (e.g. explicit user instruction issued this turn), state that"
    echo "     reasoning explicitly before retrying — this hook does not distinguish that"
    echo "     case automatically."
    echo ""
    echo "Reference: failed-attempts.md archive 'stale context reading after rewind"
    echo "  misjudged as over-threshold, causing a self-paced loop to end prematurely"
    echo "  and run cleanup' + class"
    echo "  ralph-loop-cleanup-invoked-before-promise-threshold"
  } >&2
  exit 2
fi

exit 0
