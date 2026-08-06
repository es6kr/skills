#!/usr/bin/env bash
# PreToolUse:TaskOutput — Block synchronous long blocking waits via TaskOutput's
# own `block`/`timeout` parameters.
#
# Why: TaskOutput(block=true, timeout=<large>) holds the current turn hostage
# for up to `timeout` ms without ever ending the turn. That is invisible to
# both existing idle-wait guards:
#   - bash-guard.py's TIME_BOUND_CEILING only inspects Bash tool calls
#   - block-idle-wait-without-short-cycle.sh (Stop hook) only fires when a
#     turn *ends* on a wait-phrase pattern
# A multi-minute TaskOutput(block=true) call does neither, so it silently
# reproduces the same idle-cache-ttl cost (prompt cache 5-min TTL) that both
# of those guards exist to prevent (failed-attempts.md "idle-cache-ttl", 12th
# recurrence 2026-07-30).
#
# Policy: block=true is only safe for a short confirmation check.
#   - block=false -> always allowed (non-blocking poll, any timeout value)
#   - block=true (or omitted, since the tool defaults to true) with
#     timeout > 30000 (30s) -> DENIED
#   - block=true with timeout <= 30000 -> allowed
#
# There is no bypass flag: unlike a Bash watcher, TaskOutput has no free-form
# command string to prefix an approval token into, and there is no legitimate
# case for a multi-minute synchronous TaskOutput wait — the correct move is
# always either a short block=true check, a block=false poll, or ending the
# turn with ScheduleWakeup (claudify/background-polling.md).
#
# Fail-open on parse errors so unrelated calls are never blocked.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "TaskOutput" ]]; then
  exit 0
fi

BLOCK=$(echo "$INPUT" | jq -r '.tool_input.block' 2>/dev/null)
# TaskOutput's own schema defaults `block` to true when omitted/null.
if [[ "$BLOCK" == "false" ]]; then
  exit 0
fi

TIMEOUT=$(echo "$INPUT" | jq -r '.tool_input.timeout // 30000' 2>/dev/null)
if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]]; then
  exit 0
fi

if [[ "$TIMEOUT" -gt 30000 ]]; then
  cat >&2 <<MSG
DENIED: TaskOutput(block=true, timeout=${TIMEOUT}) blocks the current turn
synchronously for up to $((TIMEOUT / 1000))s.

Why blocked (claudify/background-polling.md — TaskOutput native block/timeout):
  - A blocking TaskOutput call never ends the turn, so it is invisible to
    bash-guard.py's Bash-only ceiling and to the Stop-hook wait-phrase detector.
  - It burns the same prompt-cache-window cost (5-min TTL) as any other idle wait
    (failed-attempts.md "idle-cache-ttl", 12th recurrence).

Required action (pick one):
  1. Retry with timeout <= 30000 (a short confirmation check, not a wait-out)
  2. Use block=false for a non-blocking poll (any timeout value is fine)
  3. If the task is still running after a short check, end the turn and
     register ScheduleWakeup per the delay guide in background-polling.md,
     or drive other pending work this turn and poll again later
MSG
  exit 2
fi

exit 0
