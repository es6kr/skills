#!/usr/bin/env bash
# PreToolUse:Bash — Block background watchers whose worst-case silent runtime
# exceeds the prompt-cache TTL window, so long external-event polling doesn't
# leave the main assistant idle past the point where the next turn re-reads
# the full context uncached.
#
# Scope: only `run_in_background: true` Bash calls. A foreground call is
# already bounded by the tool's own timeout (default 120s, max 600s) and
# blocks synchronously rather than leaving the assistant idle across turns.
#
# Policy (workflow.md background-wait cache-window rule):
#   - Estimated worst-case silent duration > 240s -> DENIED
#   - Estimated worst-case silent duration <= 240s -> allow
#   - Cannot estimate (no sleep/loop pattern found) -> fail open (allow)
#
# Detection is a conservative static estimate over the command text:
#   - single bare `sleep N` -> N seconds
#   - `for ... in $(seq [A] M)` (or `{A..M}`) loop containing a `sleep N` ->
#     up to (M-A+1) * N seconds (max sleep value used if multiple)
#   - `while`/`until` loop containing `sleep N` with no discoverable bound ->
#     treated as unbounded -> DENIED regardless of N
#
# Bypass: explicit user approval for a case where a longer single silent
# window is genuinely necessary. Prefix the command with
# LONG_WATCHER_APPROVED=1 after the user has explicitly signed off.
#
# Fail-open on parse/query errors so unrelated commands are never blocked.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

RUN_BG=$(echo "$INPUT" | jq -r '.tool_input.run_in_background // false' 2>/dev/null)
if [[ "$RUN_BG" != "true" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$CMD" ]]; then
  exit 0
fi

if echo "$CMD" | grep -q 'LONG_WATCHER_APPROVED=1'; then
  exit 0
fi

VERDICT=$(WATCHER_HOOK_CMD="$CMD" python3 - <<'PY' 2>/dev/null
import os, re

cmd = os.environ.get("WATCHER_HOOK_CMD", "")

sleeps = [int(n) for n in re.findall(r'\bsleep\s+(\d+)\b', cmd)]
if not sleeps:
    print("OK:0")
    raise SystemExit(0)
max_sleep = max(sleeps)

# Loop iteration bound candidates: seq [A] M, or brace range {A..M}
bounds = []
for a, m in re.findall(r'seq\s+(?:(\d+)\s+)?(\d+)\b', cmd):
    lo = int(a) if a else 1
    hi = int(m)
    bounds.append(max(hi - lo + 1, 1))
for a, m in re.findall(r'\{(\d+)\.\.(\d+)\}', cmd):
    bounds.append(max(int(m) - int(a) + 1, 1))

has_loop = bool(re.search(r'\b(for|while|until)\b', cmd))

if bounds:
    worst = max(bounds) * max_sleep
    print(f"OK:{worst}")
elif has_loop:
    # Loop present but no discoverable bound alongside a sleep -> unbounded
    print("UNBOUNDED")
else:
    print(f"OK:{max_sleep}")
PY
)

if [[ -z "$VERDICT" ]]; then
  exit 0
fi

if [[ "$VERDICT" == "UNBOUNDED" ]]; then
  cat >&2 <<'MSG'
DENIED: background watcher has an unbounded loop with no discoverable iteration cap (while/until + sleep, no seq/{A..M} bound).

Why blocked (workflow.md background-wait cache-window rule):
  - The prompt cache has a 5-minute TTL. A silent background loop that can run past that
    window means the next turn's wake-up re-reads the full context uncached (slower + costlier).
  - Unbounded here means this hook cannot even estimate the worst case — it could run for hours.

Required action (pick one):
  1. Bound the loop with a real iteration cap (e.g. `for i in $(seq 1 N)`) so total runtime is knowable and <=240s
  2. Restructure as a short-cycle watcher: each cycle checks once, prints a status line, and exits;
     re-arm the wait either by re-invoking the same Bash call or via ScheduleWakeup (<=270s)
  3. If a single long silent wait is genuinely required and the user has explicitly approved it,
     re-run prefixed with: LONG_WATCHER_APPROVED=1 <command>

Reference: failed-attempts.md "background-wait idle cache TTL" (3rd recurrence — hook enforced).
MSG
  exit 2
fi

WORST="${VERDICT#OK:}"
if [[ "$WORST" =~ ^[0-9]+$ ]] && [[ "$WORST" -gt 240 ]]; then
  cat >&2 <<MSG
DENIED: background watcher's worst-case silent runtime (~${WORST}s) exceeds the 240s prompt-cache-safe window.

Why blocked (workflow.md background-wait cache-window rule):
  - The prompt cache has a 5-minute TTL. A silent background loop running longer than ~240s risks
    landing the next turn's wake-up on a cold cache (full context re-read, slower + costlier).
  - This applies even though the watcher is background-only — the main assistant staying idle
    across the whole window is the problem, not just synchronous blocking.

Required action (pick one):
  1. Shorten the loop so worst-case total is <=240s (fewer iterations or a shorter sleep)
  2. Restructure as a short-cycle watcher: exit each cycle with a status line after a bounded
     wait, then re-arm (re-invoke the same Bash call, or use ScheduleWakeup <=270s between checks)
  3. If a single longer silent wait is genuinely required and the user has explicitly approved it,
     re-run prefixed with: LONG_WATCHER_APPROVED=1 <command>

Reference: failed-attempts.md "background-wait idle cache TTL" (3rd recurrence — hook enforced).
MSG
  exit 2
fi

exit 0
