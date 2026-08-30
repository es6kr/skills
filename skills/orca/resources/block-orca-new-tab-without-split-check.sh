#!/bin/bash
# block-orca-new-tab-without-split-check.sh (PreToolUse:Bash)
#
# Blocks `orca worktree create ... --no-parent` and a bare `orca terminal create`
# (without `--worktree active`) unless this session already checked for a
# splittable current terminal via `orca terminal list` recently, or the caller
# explicitly opts out.
#
# Why: failed-attempts.md class=orca-terminal-split-pane-parameter-omission has
# recurred 4 times — defaulting to an independent new tab/worktree instead of
# considering `orca terminal split` into an already-active terminal first.

input=$(cat)

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
marker="${TMPDIR:-/tmp}/orca-terminal-list-checked-${session_key}"

# The command itself is a split-pane / list check — always allow, and stamp the
# marker so a follow-up create/split within the next 30 minutes doesn't
# re-trigger this gate. This must run BEFORE the create-command matching below,
# since `terminal list`/`terminal split` never match `terminal create`.
if echo "$command" | grep -qE '(^|[;&|]\s*)orca[[:space:]]+terminal[[:space:]]+(list|split)\b'; then
  touch "$marker" 2>/dev/null
  exit 0
fi

is_worktree_create=0
is_terminal_create=0
echo "$command" | grep -qE '(^|[;&|]\s*)orca[[:space:]]+worktree[[:space:]]+create\b' && is_worktree_create=1
echo "$command" | grep -qE '(^|[;&|]\s*)orca[[:space:]]+terminal[[:space:]]+create\b' && is_terminal_create=1

if [ "$is_worktree_create" -eq 0 ] && [ "$is_terminal_create" -eq 0 ]; then
  exit 0
fi

# Auditable opt-out — a genuinely independent new workspace was intended.
echo "$command" | grep -q 'ORCA_NEW_WORKSPACE_APPROVED=1' && exit 0

# `orca terminal create --worktree active` explicitly attaches to the CURRENT
# worktree, not a new one — that's already the safe path, allow it.
if [ "$is_terminal_create" -eq 1 ]; then
  echo "$command" | grep -qE -- '--worktree[[:space:]]+active' && exit 0
fi

# `orca worktree create` without `--no-parent` is a deliberate stacked/branch-
# from-current choice, not the independent-new-workspace default — allow it.
if [ "$is_worktree_create" -eq 1 ]; then
  echo "$command" | grep -qE -- '--no-parent' || exit 0
fi

if [ -f "$marker" ]; then
  now=$(date +%s)
  mtime=$(stat -f %m "$marker" 2>/dev/null || stat -c %Y "$marker" 2>/dev/null || echo 0)
  age=$(( now - mtime ))
  if [ "$age" -lt 1800 ]; then
    exit 0
  fi
fi

cat >&2 <<'EOF'
============================================================
⛔ [Safety Hook] BLOCKED: orca new-tab/new-worktree launch without a split-pane check first.

Why blocked:
  - failed-attempts.md class=orca-terminal-split-pane-parameter-omission has
    recurred 4 times: defaulting to an independent new tab/worktree instead of
    checking whether the current session already has an active terminal to
    split into.

Required action (pick one):
  1. Run `orca terminal list --json` first to check for a splittable current
     terminal, then either `orca terminal split --terminal <handle>
     --direction horizontal|vertical --command "<cmd>"` (same tab) or re-run
     this command (the list check clears this gate for 30 minutes).
  2. If a genuinely independent new workspace is intended (unrelated work, not
     meant to run alongside the current session), prefix the command with
     ORCA_NEW_WORKSPACE_APPROVED=1 so the opt-out is auditable.

Reference: failed-attempts.md class=orca-terminal-split-pane-parameter-omission (4th occurrence).
============================================================
EOF
exit 2
