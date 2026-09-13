#!/usr/bin/env bats
# Regression tests for the `git worktree add` pattern in
# block-prod-branch-autonomous-ops.sh.
#
# Scope: pattern 6 only, driven end-to-end through the guard's real stdin
# contract (a PreToolUse Bash payload) so the exit code under test is the one
# the harness actually sees.
#
# The hazard: `git worktree add <path> -b <new-branch> <start-point>` names the
# start-point last. When that start-point is a protected branch the guard saw
# "master" in trailing position and denied, even though the command creates a
# *new* branch and never writes to the protected one. Creating a feature branch
# off master is the single most ordinary thing a contributor does here, so a
# guard that blocks it teaches people to reach for ALLOW_PROD_BRANCH_OPS=1 on
# routine work — which is exactly the escape hatch that must stay rare to mean
# anything.
#
# What must still be denied: the protected name appearing as the branch being
# *created* (`-b master`, `-B master`), and a bare checkout of the protected
# branch into a new worktree (`git worktree add <path> master`).

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/hook-kit/resources/block-prod-branch-autonomous-ops.sh"

setup() {
  [ -f "$GUARD" ] || skip "guard not found: $GUARD"
  command -v jq >/dev/null || skip "jq not available"
}

# Feeds a Bash command to the guard. Echoes the exit status.
run_guard() {
  local cmd="$1"
  local payload
  payload="$(jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}')"
  printf '%s' "$payload" | env -u ALLOW_PROD_BRANCH_OPS bash "$GUARD" >/dev/null 2>&1
  echo $?
}

# --- allowed: protected name is only the start-point -----------------------

@test "worktree add with -b creating a feature branch off master is allowed" {
  [ "$(run_guard 'git worktree add .worktrees/feat-x -b feat/x origin/master')" = "0" ]
}

@test "worktree add with -b off bare master is allowed" {
  [ "$(run_guard 'git worktree add .worktrees/feat-x -b feat/x master')" = "0" ]
}

@test "worktree add with -b off origin/production is allowed" {
  [ "$(run_guard 'git worktree add .worktrees/feat-x -b feat/x origin/production')" = "0" ]
}

@test "worktree add with -b and trailing redirection off master is allowed" {
  [ "$(run_guard 'git worktree add .worktrees/feat-x -b feat/x origin/master 2>&1 | tail -2')" = "0" ]
}

@test "worktree add with path after the -b flag is allowed" {
  [ "$(run_guard 'git worktree add -b feat/x .worktrees/feat-x origin/master')" = "0" ]
}

# --- still denied: protected name is the branch being created --------------

@test "worktree add creating a branch named master is denied" {
  [ "$(run_guard 'git worktree add .worktrees/m -b master origin/develop')" = "2" ]
}

@test "worktree add force-creating a branch named production is denied" {
  [ "$(run_guard 'git worktree add .worktrees/m -B production origin/develop')" = "2" ]
}

# --- still denied: bare checkout of a protected branch ---------------------

@test "worktree add checking out master without -b is denied" {
  [ "$(run_guard 'git worktree add .worktrees/m master')" = "2" ]
}

@test "worktree add checking out release without -b is denied" {
  [ "$(run_guard 'git worktree add .worktrees/m release')" = "2" ]
}

# --- unrelated patterns must not regress ----------------------------------

@test "git push to master is still denied" {
  [ "$(run_guard 'git push origin master')" = "2" ]
}

@test "git checkout -b master is still denied" {
  [ "$(run_guard 'git checkout -b master')" = "2" ]
}

@test "ALLOW_PROD_BRANCH_OPS=1 prefix still overrides" {
  [ "$(run_guard 'ALLOW_PROD_BRANCH_OPS=1 git worktree add .worktrees/m master')" = "0" ]
}
