#!/usr/bin/env bash
# Stop — Block ending a turn in a silent-wait posture while background work is
# in flight, without a short-cycle watcher or a drivable pending item driven.
#
# Background: "main assistant idles while background tasks run -> prompt cache
# (5-min TTL) expires -> every wake-up re-reads full context uncached" recurred
# 4 times across wip/resume, next, and watcher-design domains. The escalation
# policy mandates a hook at 4+ recurrences; this hook is that enforcement.
# See failed-attempts.md "background-wait idle cache TTL" family.
#
# Contract:
#   BLOCK when ALL hold:
#     1. This turn dispatched background work, OR handed a command off to the
#        user's own terminal — transcript tail carries a background marker
#        ("Command running in background with ID:" from a Bash
#        run_in_background, "The agent is now running" from an Agent spawn,
#        a GitHub Actions run in flight), OR the final assistant text
#        contains a "! <command>" handoff line (idle-cache-ttl class, shape:
#        user-!-handoff — the user's own async execution is invisible to this
#        transcript, but carries the identical cache-expiry risk).
#     2. The LAST assistant text ends the turn in a waiting posture — matches
#        a waiting-phrase pattern (Korean phrases load from the git-ignored
#        locale data file; English-only fallback below). Waived when marker 1
#        was the "!"-handoff line itself — that is inherently a wait posture.
#     3. No explicit idle-ok annotation: the final text lacks "[idle-ok]".
#   Escapes:
#     - Drive a drivable pending item in the same turn (final text is then a
#       work report, not a waiting phrase).
#     - Re-arm the wait as a short cycle (<= 240 s timeout, end -> notify ->
#       re-arm) and say so in the final text without a bare waiting close.
#     - Genuinely nothing drivable AND expected wait fits the cache window:
#       append "[idle-ok]" to the final text (documented judgment, not a
#       silent default).

INPUT=$(cat)

if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]] || exit 0

# Locale patterns (git-ignored data file; English-only fallback below).
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then . "$HG_DATA_FILE"; fi
WAIT_PHRASES="${HG_IDLE_WAIT_PHRASES:-(wait(ing)? (for|on)|will (resume|continue) (when|once)|resume once|until (it|they) complete|won'?t (poll|check)|not (going to |gonna )?(poll|check)|no need to (poll|check)|i'?ll (wait|check back) (for|when))}"

TAIL=$(tail -n 200 "$TRANSCRIPT_PATH" 2>/dev/null)

# 1. Background dispatch marker anywhere in the recent tail — either Claude
#    Code's own native background dispatch (Bash run_in_background, Agent
#    spawn), OR evidence that a synchronous tool call just triggered an
#    external async system (a GitHub Actions run) that is now in flight
#    outside Claude Code's own tracking. The latter is a distinct shape from
#    the former — `git push` triggering a workflow returns immediately, so
#    there is no run_in_background/Agent marker to match, yet the same
#    idle-cache-TTL risk applies once the turn ends on a "stopping" close
#    with no re-check plan (idle-cache-ttl class, shape N — see
#    failed-attempts.md).
#    The GH-run signal is anchored on "databaseId" (a `gh run list`/`gh run
#    view --json` field unique to workflow-run objects) co-occurring with
#    status:"in_progress" — a bare `"status":"in_progress"` alone is FAR too
#    broad and false-positives on ordinary `TaskUpdate(status:"in_progress")`
#    tool calls, which occur on essentially every multi-step turn.
GH_RUN_INFLIGHT_RE='\\?"databaseId\\?":[0-9]+.{0,200}\\?"status\\?":\\?"in_progress\\?"|\\?"status\\?":\\?"in_progress\\?".{0,200}\\?"databaseId\\?":[0-9]+'

# 2. Last assistant text — single most-recent non-empty text entry, trailing
#    300 chars only (waiting closes sit at the end; mid-body mentions of
#    waiting in long reports must not trigger). Computed before the marker
#    gate below because marker 1c reads this same text.
LAST_TEXT=$(printf '%s' "$TAIL" | jq -rs '
  [ .[] | select(type=="object" and .type=="assistant")
    | (.message.content
       | if type == "array" then ([.[] | select(.type? == "text") | .text] | join(" "))
         elif type == "string" then . else "" end)
    | select(length > 0)
  ] | last // "" | .[-300:]
' 2>/dev/null)

# 1c. User-interactive `!` command handoff marker — a turn that asks the user
#     to run a shell command themselves (via the `!` prefix convention) hands
#     the actual work to the user's own terminal, invisible to this
#     transcript until they report back. No run_in_background/Agent/GH-run
#     marker exists for this shape (idle-cache-ttl class, shape: user-!-
#     handoff — see failed-attempts.md). Detected as a line in the final
#     assistant text starting with "! " followed by a non-space char — the
#     established handoff convention, low false-positive risk.
BANG_HANDOFF=0
if [[ -n "$LAST_TEXT" ]] && printf '%s' "$LAST_TEXT" | grep -qE '^! [^ ]'; then
  BANG_HANDOFF=1
fi

if ! printf '%s' "$TAIL" | grep -qE 'Command running in background with ID:|Async agent launched successfully|The agent is (now running|working in the background)' \
   && ! printf '%s' "$TAIL" | grep -qEz "$GH_RUN_INFLIGHT_RE" \
   && [[ "$BANG_HANDOFF" -eq 0 ]]; then
  exit 0
fi

[[ -n "$LAST_TEXT" ]] || exit 0

# 3. Explicit idle-ok annotation allows the wait.
if printf '%s' "$LAST_TEXT" | grep -qF '[idle-ok]'; then
  exit 0
fi

# 4. Waiting-posture close? A bare `!`-handoff line at turn-end is inherently
#    a wait posture by construction (nothing else to do until the user
#    responds) — skip the WAIT_PHRASES requirement for that marker specifically.
if [[ "$BANG_HANDOFF" -eq 0 ]] && ! printf '%s' "$LAST_TEXT" | grep -qiE "$WAIT_PHRASES"; then
  exit 0
fi

REASON="Turn is closing in a silent-wait posture while background work is in flight — idling past ~5 minutes expires the prompt cache (5-min TTL). Pick one before ending: (1) drive a drivable pending/deferred item in this turn (multiSelect-unselected items are deferred candidates, not declined); (2) re-arm the wait as a short cycle — timeout <= 240 s, end -> notify -> re-arm — instead of one long silent watcher; (3) if nothing is drivable AND the expected wait fits the cache window, state that judgment and append [idle-ok] to the final text."
jq -cn --arg r "$REASON" '{decision:"block", reason:$r}'
exit 0
