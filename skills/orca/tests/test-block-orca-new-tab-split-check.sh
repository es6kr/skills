#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
GUARD="$ROOT/resources/block-orca-new-tab-without-split-check.sh"

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

PASS=0
FAIL=0

run_case() {
  local command=$1 expected=$2 output
  output=$(printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$command" \
    | TMPDIR="$TMPROOT" "$GUARD" 2>&1 || true)
  if [[ "$expected" == blocked ]]; then
    if grep -q 'BLOCKED: orca new-tab/new-worktree launch' <<<"$output"; then
      PASS=$((PASS + 1))
    else
      FAIL=$((FAIL + 1))
      printf 'FAIL (expected blocked): %s\n' "$command" >&2
    fi
  else
    if [[ -z "$output" ]]; then
      PASS=$((PASS + 1))
    else
      FAIL=$((FAIL + 1))
      printf 'FAIL (expected allowed): %s\n  got: %s\n' "$command" "$output" >&2
    fi
  fi
}

# --- Every create path is gated -------------------------------------------
# `--worktree active` avoids creating a new WORKTREE but still opens a new TAB,
# which is the behaviour this guard exists to gate, so it must not short-circuit.
run_case 'orca terminal create --command claude' blocked
run_case 'orca terminal create --worktree active --command claude' blocked
run_case 'orca terminal create --worktree=active --command claude' blocked
run_case 'orca worktree create --no-parent --name task' blocked
run_case 'orca-ide terminal create --worktree active --command claude' blocked
run_case 'orca-dev worktree create --no-parent --name task' blocked

# --- Regression: a `terminal list` must NOT clear the gate -----------------
# This is the defect that let the class keep recurring with the hook installed.
# The block message's own remedy #1 was to run `terminal list`, which stamped a
# marker that passed every create for the next 30 minutes — so following the
# advice disarmed the gate. A list is now just a list.
run_case 'orca terminal list --json' allowed
run_case 'orca terminal create --worktree active --command claude' blocked
run_case 'orca-ide terminal list --json' allowed
run_case 'orca-ide terminal create --command claude' blocked
run_case 'orca worktree create --no-parent --name task' blocked

# --- Named exceptions are the only way through -----------------------------
# Each flag states which documented case applies, so the choice is auditable.
run_case 'ORCA_PANE_LIMIT_REACHED=1 orca terminal create --command claude' allowed
run_case 'ORCA_NEW_WORKSPACE_APPROVED=1 orca terminal create --worktree active --command claude' allowed
run_case 'ORCA_FILE_CONFLICT=1 orca worktree create --no-parent --name task' allowed

# --- Non-create commands stay allowed --------------------------------------
run_case 'orca terminal split --direction vertical' allowed
run_case 'orca terminal split --terminal term_abc --direction vertical --command claude' allowed
run_case 'orca worktree create --repo id:x --name plan' allowed
run_case 'orca status --json' allowed
run_case 'orca repo list --json' allowed

# --- Quoted literals naming a create are not a create ----------------------
run_case 'echo "orca terminal create --command claude"' allowed

printf '%d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
