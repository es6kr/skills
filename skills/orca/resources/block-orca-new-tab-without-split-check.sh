#!/bin/bash
# block-orca-new-tab-without-split-check.sh (PreToolUse:Bash)
#
# Blocks `orca worktree create ... --no-parent` and a bare `orca terminal create`
# (without `--worktree active`) unless this session already checked for a
# splittable current terminal via `orca terminal list` recently, or the caller
# explicitly opts out.
#
# Why: failed-attempts.md class=orca-terminal-split-pane-parameter-omission has
# recurred repeatedly — defaulting to an independent new tab/worktree instead
# of considering `orca terminal split` into an already-active terminal first.
# Also matches CLI-resolution aliases (orca-ide / orca-dev / $ORCA_CLI_COMMAND)
# per the orca skill's own "Resolve the CLI" guidance — a bare-`orca`-only
# match let commands built that way bypass this gate entirely.

input=$(cat)

# The orca skill's own "Resolve the CLI" procedure instructs callers to invoke
# the resolved binary (orca-ide / orca-dev / $ORCA_CLI_COMMAND's value), not
# always bare `orca` — a command built by following that guidance must still
# be recognized here, or the hook silently never fires for it.
orca_bin_pattern='orca-ide|orca-dev|orca'
if [ -n "$ORCA_CLI_COMMAND" ]; then
  orca_cli_escaped=$(printf '%s' "$ORCA_CLI_COMMAND" | sed 's/[][\.^$*+()?{}|/]/\\&/g')
  orca_bin_pattern="${orca_cli_escaped}|${orca_bin_pattern}"
fi

command=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
ti = d.get("tool_input") or {}
print(ti.get("command") or d.get("command") or "")
' 2>/dev/null)

[ -z "$command" ] && exit 0

# Quoted literals (e.g. `echo '; orca terminal list'`) must not satisfy any
# guard match below — a string literal being echoed is not the command it
# names. Strip single- and double-quoted spans before matching (heuristic:
# no nested/escaped-quote handling, consistent with the other regex-based
# guards in this hook family).
sanitized_command=$(printf '%s' "$command" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g")

transcript_path=$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    sys.exit(0)
print(d.get("transcript_path") or "")
' 2>/dev/null)

session_key=$(printf '%s' "$transcript_path" | shasum 2>/dev/null | cut -d" " -f1)
[ -z "$session_key" ] && session_key="nosession"
# NOTE (marker removal): this gate used to stamp a 30-minute marker whenever
# `orca terminal list` ran, and then let ANY create pass while that marker was
# fresh. That inverted the gate's purpose. What the gate asks is not "did you
# look?" but "did you act on what you saw by splitting?" — and listing is the
# precondition for splitting, not a substitute for it. Worse, the block message
# below advertised that very list command as the way to clear the gate, so an
# agent that followed the instruction faithfully disarmed the guard for the
# next 30 minutes and then created a new tab unchallenged. Observed repeatedly
# (class=orca-terminal-split-pane-parameter-omission); the marker is therefore
# gone, and creating a new tab/worktree now always requires the auditable
# opt-out below.

env_prefix="([A-Za-z_][A-Za-z0-9_]*=[^;&|[[:space:]]]*[[:space:]]+)*"
is_worktree_create=0
is_terminal_create=0
echo "$sanitized_command" | grep -qE "(^|[;&|][[:space:]]*)${env_prefix}(${orca_bin_pattern})[[:space:]]+worktree[[:space:]]+create\b" && is_worktree_create=1
echo "$sanitized_command" | grep -qE "(^|[;&|][[:space:]]*)${env_prefix}(${orca_bin_pattern})[[:space:]]+terminal[[:space:]]+create\b" && is_terminal_create=1

if [ "$is_worktree_create" -eq 0 ] && [ "$is_terminal_create" -eq 0 ]; then
  exit 0
fi

# Auditable opt-out — a genuinely independent new target was intended.
#
# One variable covers BOTH kinds of new target this gate guards: a new tab
# (`terminal create`) and a new worktree (`worktree create --no-parent`). The
# older name said "WORKSPACE", which read as covering only the tab case and left
# the worktree case looking unauthorized by the same flag. ORCA_NEW_TARGET_APPROVED
# is the canonical name; the legacy name is still accepted so in-flight sessions
# and older notes keep working.
#
# Must be attached to the guarded create command, not an earlier command.
echo "$sanitized_command" | grep -qE "(^|[;&|][[:space:]]*)${env_prefix}(ORCA_NEW_TARGET_APPROVED|ORCA_NEW_WORKSPACE_APPROVED)=1([[:space:]]+[A-Za-z_][A-Za-z0-9_]*=[^;&|[[:space:]]]*)*[[:space:]]+(${orca_bin_pattern})[[:space:]]+(terminal|worktree)[[:space:]]+create\b" && exit 0

# NOTE: `--worktree active` is deliberately NOT an exemption here. It attaches to
# the CURRENT worktree instead of creating a new one, but it still opens a new
# TAB — and a new tab without first checking whether the current terminal is
# splittable is exactly what this guard gates (see its name). Treating it as a
# safe path let the whole gate be bypassed by appending one flag. It now falls
# through to the block below like any other create; split into the current
# terminal instead, or use the auditable opt-out above.

# `orca worktree create` without `--no-parent` is a deliberate stacked/branch-
# from-current choice, not the independent-new-workspace default — allow it.
if [ "$is_worktree_create" -eq 1 ]; then
  echo "$sanitized_command" | grep -qE -- '--no-parent' || exit 0
fi

cat >&2 <<'EOF'
============================================================
⛔ [Safety Hook] BLOCKED: orca new-tab/new-worktree launch without a split-pane check first.

Why blocked:
  - failed-attempts.md class=orca-terminal-split-pane-parameter-omission has
    recurred repeatedly: defaulting to an independent new tab/worktree instead
    of checking whether the current session already has an active terminal to
    split into.

Required action (pick one):
  1. DEFAULT — split into the current tab instead of opening a new one:
       orca terminal list --json                  # find the handle, count panes
       orca terminal split --terminal <handle> \
         --direction vertical --command "<cmd>"   # up to 4 panes per tab
     Listing alone does NOT clear this gate (it used to, for 30 minutes — that
     is exactly how this guard kept getting disarmed). Splitting is the action
     the gate is asking for; listing is only how you find the handle.
  2. If a genuinely independent new target is intended, prefix the command with
     ORCA_NEW_TARGET_APPROVED=1 so the opt-out is auditable. Only three reasons
     qualify, and you should be able to name which one in a sentence:
       (a) the current tab already holds 4 panes (the limit)
       (b) the user explicitly asked for a new tab/worktree
       (c) a real file conflict (the same files must be edited concurrently)
     "The target repo/topic is unrelated to the current panes" is NOT a fourth
     reason, and neither is "the repo is not registered with Orca".

Reference: failed-attempts.md class=orca-terminal-split-pane-parameter-omission.
============================================================
EOF
exit 2
