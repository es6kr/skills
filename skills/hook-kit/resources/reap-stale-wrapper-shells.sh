#!/usr/bin/env bash
# Stop — silently reap leaked Bash-tool wrapper shells.
#
# Observed defect (2026-07-16, es6kr claude-code-sessions PR #199 session):
# a Bash tool call's actual payload completes and its output is captured
# normally, but the wrapper `zsh -c source .../shell-snapshots/snapshot-zsh-*`
# process itself sometimes never exits — it hangs on the harness's own
# trailing cwd-tracking line (`pwd -P >| /tmp/claude-*-cwd`) appended after
# every command. Over a long session these accumulate silently; 7 were found
# spanning 24 minutes to 8+ hours old, all confirmed idle with their real
# work already done.
#
# This hook self-heals the leak every turn instead of letting it accumulate
# for hours before anyone notices. It is intentionally silent (no
# decision:block, no message) — a routine reap is not worth interrupting the
# turn for. Fails open on any error (never blocks Stop).
#
# Safety — four joint criteria, all must hold before a process is killed:
#   1. Command matches the exact harness wrapper signature
#      (shell-snapshots/snapshot-zsh) — a signature no real user process
#      would ever incidentally match, so blast radius is contained to
#      Claude-Code-spawned shells only.
#   2. Age exceeds 10 minutes (600s) — comfortably above the ~4 minute
#      ceiling of any legitimate build/test/push/watch observed in this
#      environment, and above the 240s cap this environment's own
#      block-long-silent-watcher.sh hook already enforces on intentional
#      long background waits.
#   3. Process state starts with 'S' (sleeping/idle) — a genuinely
#      still-computing process (state 'R') is never touched, regardless of
#      age.
#   4. No live child process — a leaked wrapper has already finished its
#      payload and hangs on the trailing cwd-tracking builtin (no child),
#      whereas a LIVE background job's wrapper still has its running payload
#      as a child and is ALSO in state 'S' (blocked in wait()). State alone
#      (criterion 3) cannot tell them apart, so a childless-wrapper gate is
#      required to never reap an actively-running background job.
#
# Input (stdin): JSON { session_id, transcript_path, stop_hook_active }
# Output (stdout): always empty — this hook never surfaces a message.
#
# Responsibility: hook-kit skill (general/system hook, no domain owner).
# Install: `Skill("hook-kit", "install")` — Stop matcher, direct-registration
# pattern (command points at this resources/ path).

set -uo pipefail

THRESHOLD_SECONDS=600

# ps STATE,ETIMES,COMMAND — BSD ps (macOS) syntax. Fields: stat, elapsed
# seconds, then the full command starting at a fixed offset we split on.
ps -eo pid=,stat=,etime=,command= 2>/dev/null | while IFS= read -r line; do
  pid=$(awk '{print $1}' <<<"$line")
  stat=$(awk '{print $2}' <<<"$line")
  etime=$(awk '{print $3}' <<<"$line")
  cmd=$(cut -d' ' -f4- <<<"$line")

  [[ -z "$pid" || -z "$stat" || -z "$etime" ]] && continue

  # Command signature check (criterion 1)
  [[ "$cmd" != *"shell-snapshots/snapshot-zsh"* ]] && continue

  # State check (criterion 3) — must be sleeping, never touch a running proc
  [[ "$stat" != S* ]] && continue

  # Age check (criterion 2) — etime formats: SS, MM:SS, HH:MM:SS, DD-HH:MM:SS
  # NOTE: values are forced to base-10 via `10#` — bash's $(( )) treats a
  # leading-zero literal (e.g. "08", "09") as octal, and 8/9 are not valid
  # octal digits, causing a hard arithmetic error. Confirmed reproducible:
  # 3 of the first 7 real zombie shells this hook was written for had
  # etimes like "08:05:55" that would have crashed this exact computation.
  secs=0
  if [[ "$etime" == *-* ]]; then
    days="${etime%%-*}"
    rest="${etime#*-}"
    secs=$((10#$days * 86400))
    etime="$rest"
  fi
  IFS=':' read -ra parts <<<"$etime"
  case "${#parts[@]}" in
    3) secs=$((secs + 10#${parts[0]}*3600 + 10#${parts[1]}*60 + 10#${parts[2]})) ;;
    2) secs=$((secs + 10#${parts[0]}*60 + 10#${parts[1]})) ;;
    1) secs=$((secs + 10#${parts[0]})) ;;
  esac

  [[ "$secs" -lt "$THRESHOLD_SECONDS" ]] && continue

  # Liveness check (criterion 4) — never reap a wrapper that still has a live
  # child: that child is a running background payload, so the wrapper's 'S'
  # state is active-wait, not a leak. A leaked wrapper finished its payload and
  # hangs on a builtin, so it has no children.
  [[ -n "$(pgrep -P "$pid" 2>/dev/null)" ]] && continue

  kill "$pid" 2>/dev/null || true
done

exit 0
