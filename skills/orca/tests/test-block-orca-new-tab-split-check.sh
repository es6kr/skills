#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
GUARD="$ROOT/resources/block-orca-new-tab-without-split-check.sh"

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

passed=0
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
  passed=$((passed + 1))
}

# --- Without the opt-out, every new-target path is gated --------------------
# `--worktree active` avoids creating a new WORKTREE but still opens a new TAB,
# which is the behaviour this guard exists to gate, so it is not an exemption.
run_case 'orca terminal create --command claude' blocked
run_case 'orca terminal create --worktree active --command claude' blocked
run_case 'orca terminal create --worktree=active --command claude' blocked
run_case 'orca worktree create --no-parent --name task' blocked
run_case 'orca-ide terminal create --worktree active --command claude' blocked
run_case 'orca-dev worktree create --no-parent --name task' blocked

# --- One opt-out variable covers BOTH new-target kinds ---------------------
# The older name read as covering only the tab case, leaving the worktree case
# looking unauthorized by the same flag; one name now covers both.
run_case 'ORCA_NEW_TARGET_APPROVED=1 orca terminal create --worktree active --command claude' allowed
run_case 'ORCA_NEW_TARGET_APPROVED=1 orca worktree create --no-parent --name task' allowed
# The legacy name stays accepted so in-flight sessions and older notes keep working.
run_case 'ORCA_NEW_WORKSPACE_APPROVED=1 orca terminal create --worktree active --command claude' allowed

# --- Non-create commands stay allowed -------------------------------------
run_case 'orca worktree create --repo id:x --name plan' allowed
run_case 'orca terminal split --direction vertical' allowed
run_case 'orca terminal list --json' allowed

# --- Regression: listing must NOT clear the gate --------------------------
# This guard used to stamp a 30-minute marker whenever `terminal list` ran and
# then let any new-target command through while that marker was fresh, while its
# own block message advertised that same list command as the remedy. An agent
# that followed the instruction faithfully therefore disarmed the guard and then
# opened a new tab unchallenged. What the gate asks is not "did you look?" but
# "did you act on what you saw by splitting?" — listing is how you find a handle
# to split into, never a substitute for splitting.
run_case 'orca terminal list --json' allowed
run_case 'orca terminal create --worktree active --command claude' blocked
run_case 'orca terminal create --command claude' blocked
run_case 'orca-ide terminal create --worktree active --command claude' blocked
run_case 'orca worktree create --no-parent --name task' blocked

# Splitting likewise does not pre-authorize a later new-target command.
run_case 'orca terminal split --terminal term_abc --direction vertical' allowed
run_case 'orca terminal create --command claude' blocked

# --- Quoted literals must not satisfy any guard match --------------------
run_case "echo 'orca terminal list'; orca terminal create --command claude" blocked

# --- Compound commands with list/split must not bypass create gate ---------
run_case 'orca terminal list; orca terminal create --command claude' blocked
run_case 'orca terminal split --direction vertical && orca terminal create --command claude' blocked

# --- Approval must be bound to the guarded create command -----------------
run_case 'ORCA_NEW_TARGET_APPROVED=1 true; orca terminal create --command claude' blocked
run_case 'ORCA_NEW_WORKSPACE_APPROVED=1 true; orca terminal create --command claude' blocked

printf '%d/%d passed\n' "$passed" "$passed"
