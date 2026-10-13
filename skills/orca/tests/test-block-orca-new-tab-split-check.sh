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
  output=$(python3 -c 'import json, sys; print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))' "$command" \
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

# --- Without the opt-out, every new-target path is gated --------------------
# `--worktree active` avoids creating a new WORKTREE but still opens a new TAB,
# which is the behaviour this guard exists to gate, so it is not an exemption.
run_case 'orca terminal create --command claude' blocked
run_case 'orca terminal create --worktree active --command claude' blocked
run_case 'orca terminal create --worktree=active --command claude' blocked
run_case 'orca worktree create --no-parent --name task' blocked
run_case 'orca-ide terminal create --worktree active --command claude' blocked
run_case 'orca-dev worktree create --no-parent --name task' blocked

# --- Opt-out flags cover new-target kinds ----------------------------------
# The canonical unified variable covers both tab and worktree creation.
run_case 'ORCA_NEW_TARGET_APPROVED=1 orca terminal create --worktree active --command claude' allowed
run_case 'ORCA_NEW_TARGET_APPROVED=1 orca worktree create --no-parent --name task' allowed
# The legacy alias stays accepted so in-flight sessions keep working.
run_case 'ORCA_NEW_WORKSPACE_APPROVED=1 orca terminal create --worktree active --command claude' allowed
# Named exceptions are also accepted for fine-grained auditability.
run_case 'ORCA_PANE_LIMIT_REACHED=1 orca terminal create --command claude' allowed
run_case 'ORCA_FILE_CONFLICT=1 orca worktree create --no-parent --name task' allowed

# --- Non-create commands stay allowed --------------------------------------
run_case 'orca worktree create --repo id:x --name plan' allowed
run_case 'orca terminal split --direction vertical' allowed
run_case 'orca terminal split --terminal term_abc --direction vertical' allowed
run_case 'orca terminal split --terminal term_abc --direction vertical --command claude' allowed
run_case 'orca terminal list --json' allowed
run_case 'orca status --json' allowed
run_case 'orca repo list --json' allowed

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
run_case 'orca-ide terminal list --json' allowed
run_case 'orca-ide terminal create --command claude' blocked
run_case 'orca-ide terminal create --worktree active --command claude' blocked
run_case 'orca worktree create --no-parent --name task' blocked

# Splitting likewise does not pre-authorize a later new-target command.
run_case 'orca terminal split --terminal term_abc --direction vertical' allowed
run_case 'orca terminal create --command claude' blocked

# --- Quoted literals naming a create are not a create ----------------------
run_case "echo 'orca terminal list'; orca terminal create --command claude" blocked
run_case 'echo "orca terminal create --command claude"' allowed
run_case 'orca terminal create --command "claude --model opus"' blocked

# --- Compound commands with list/split must not bypass create gate ---------
run_case 'orca terminal list; orca terminal create --command claude' blocked
run_case 'orca terminal split --direction vertical && orca terminal create --command claude' blocked

# --- Approval must be bound to the guarded create command -----------------
run_case 'ORCA_NEW_TARGET_APPROVED=1 true; orca terminal create --command claude' blocked
run_case 'ORCA_NEW_WORKSPACE_APPROVED=1 true; orca terminal create --command claude' blocked

printf '%d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
