#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
GUARD="$ROOT/resources/block-orca-new-tab-without-split-check.sh"

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

run_case() {
  local command=$1 expected=$2 output
  output=$(printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$command" \
    | TMPDIR="$TMPROOT" "$GUARD" 2>&1 || true)
  if [[ "$expected" == blocked ]]; then
    grep -q 'BLOCKED: orca new-tab/new-worktree launch' <<<"$output" \
      || { printf 'FAIL (expected blocked): %s\n' "$command" >&2; return 1; }
  else
    [[ -z "$output" ]] \
      || { printf 'FAIL (expected allowed): %s\n  got: %s\n' "$command" "$output" >&2; return 1; }
  fi
}

# Each scenario starts from a session that has not run `orca terminal list` yet.
clear_marker() { rm -f "$TMPROOT"/orca-terminal-list-checked-*; }

# --- Without a prior split check, every create path is gated ---------------
# `--worktree active` avoids creating a new WORKTREE but still opens a new TAB,
# which is the behaviour this guard exists to gate. It must not short-circuit
# the marker check.
clear_marker
run_case 'orca terminal create --command claude' blocked
clear_marker
run_case 'orca terminal create --worktree active --command claude' blocked
clear_marker
run_case 'orca terminal create --worktree=active --command claude' blocked
clear_marker
run_case 'orca worktree create --no-parent --name task' blocked
clear_marker
run_case 'orca-ide terminal create --worktree active --command claude' blocked

# --- Explicit opt-out and non-create commands stay allowed -----------------
clear_marker
run_case 'ORCA_NEW_WORKSPACE_APPROVED=1 orca terminal create --worktree active --command claude' allowed
clear_marker
run_case 'orca worktree create --repo id:x --name plan' allowed
clear_marker
run_case 'orca terminal split --direction vertical' allowed

# --- After a `terminal list` check, creates are allowed for 30 minutes -----
clear_marker
run_case 'orca terminal list --json' allowed
run_case 'orca terminal create --worktree active --command claude' allowed
run_case 'orca terminal create --command claude' allowed

printf '11/11 passed\n'
