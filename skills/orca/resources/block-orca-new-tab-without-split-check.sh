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
#
# The gate used to clear itself: running `orca terminal list` stamped a marker
# that passed every create for the next 30 minutes, and remedy #1 in the block
# message was to run exactly that command. Following the hook's own advice
# therefore disarmed it, which is how the class kept recurring with the hook
# installed and registered. The marker pass is gone; a create now needs one of
# three named exceptions, each naming which of the documented cases applies:
#
#   ORCA_PANE_LIMIT_REACHED=1   the current tab already holds 4 panes
#   ORCA_NEW_WORKSPACE_APPROVED=1  the user explicitly asked for a new tab/worktree
#   ORCA_FILE_CONFLICT=1        the two sessions must edit the same files
#
# Checking the pane count is still the first step — `orca terminal list --json`
# reports `tabId` per terminal, and panes in the same tab share it. The gate no
# longer treats having looked as permission to skip splitting.

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

# The command itself is a split-pane / list check — always allow. It is never a
# create, so it has nothing to gate. Note what is deliberately NOT happening
# here any more: no marker is stamped, because a later create must stand on its
# own named exception rather than on the fact that a list ran first.
if echo "$sanitized_command" | grep -qE "(^|[;&|]\s*)(${orca_bin_pattern})[[:space:]]+terminal[[:space:]]+(list|split)\b"; then
  exit 0
fi

is_worktree_create=0
is_terminal_create=0
echo "$sanitized_command" | grep -qE "(^|[;&|]\s*)(${orca_bin_pattern})[[:space:]]+worktree[[:space:]]+create\b" && is_worktree_create=1
echo "$sanitized_command" | grep -qE "(^|[;&|]\s*)(${orca_bin_pattern})[[:space:]]+terminal[[:space:]]+create\b" && is_terminal_create=1

if [ "$is_worktree_create" -eq 0 ] && [ "$is_terminal_create" -eq 0 ]; then
  exit 0
fi

# Auditable opt-outs — exactly one of the three documented exceptions. Each flag
# names which case applies, so the choice is reviewable in the transcript rather
# than being a single catch-all token. "The new session's work is unrelated to
# what the current panes are doing" is NOT one of them: below the pane limit,
# splitting is the default regardless of topic.
echo "$sanitized_command" | grep -qE 'ORCA_PANE_LIMIT_REACHED=1|ORCA_NEW_WORKSPACE_APPROVED=1|ORCA_FILE_CONFLICT=1' && exit 0

# NOTE: `--worktree active` is deliberately NOT an exemption here. It attaches to
# the CURRENT worktree instead of creating a new one, but it still opens a new
# TAB — and a new tab without first checking whether the current terminal is
# splittable is exactly what this guard gates (see its name). Treating it as a
# safe path let the whole gate be bypassed by appending one flag. It now falls
# through to the block below like any other create: split into the current tab,
# or declare one of the three named exceptions above.

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
  1. Split instead. `orca terminal list --json` reports a `tabId` per terminal;
     panes sharing your tabId are your tab's panes. Below 4, splitting is the
     default:
       orca terminal split --terminal <handle> --direction vertical --command "<cmd>"
     A split needs no selector beyond the handle, so it also works where the
     workspace is open as a plain folder and no git worktree is registered.
  2. If one of the three documented exceptions genuinely applies, prefix the
     command with the flag that names it, so the choice is auditable:
       ORCA_PANE_LIMIT_REACHED=1      the tab already holds 4 panes
       ORCA_NEW_WORKSPACE_APPROVED=1  the user explicitly asked for a new tab
       ORCA_FILE_CONFLICT=1           both sessions must edit the same files
     "Unrelated work" is not an exception — below the pane limit, split.

Note: running `orca terminal list` no longer clears this gate. It used to, which
meant following remedy #1 disarmed the hook for 30 minutes and the pattern kept
recurring with the hook installed.

Reference: failed-attempts.md class=orca-terminal-split-pane-parameter-omission.
============================================================
EOF
exit 2
