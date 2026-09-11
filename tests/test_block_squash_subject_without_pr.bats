#!/usr/bin/env bats
# Behavioral tests for block-squash-subject-without-pr.sh.
#
# The guard must fire only when `gh pr merge ... --squash` is the command
# actually being executed — not when that text merely appears as data inside a
# heredoc body, a string literal, or a comment.
#
# Origin: fix_plan.md "block-squash-subject-without-pr.sh false-positive on
# literal test-fixture text" — during a 2026-09-07 session, a python heredoc
# carrying hook test-fixture strings tripped this guard twice, because the
# grep prefilter matched raw command text with no shell-boundary awareness.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/hook-kit/resources/block-squash-subject-without-pr.sh"

_run_guard() {
  local command="$1"
  run bash "$GUARD" <<EOF
{"tool_name":"Bash","tool_input":{"command":$(printf '%s' "$command" | jq -Rs .)}}
EOF
}

@test "guard script exists" {
  [ -f "$GUARD" ]
}

# --- true positives (must still block) -------------------------------------

@test "squash merge without --subject is blocked" {
  _run_guard 'gh pr merge 470 -R es6kr/skills --squash'
  [ "$status" -eq 2 ]
}

@test "squash merge whose subject lacks the (#N) suffix is blocked" {
  _run_guard 'gh pr merge 470 -R es6kr/skills --squash --subject "fix(hook-kit): tighten the guard"'
  [ "$status" -eq 2 ]
}

@test "squash merge with --subject= form lacking the suffix is blocked" {
  _run_guard 'gh pr merge 470 --squash --subject=fix-without-suffix'
  [ "$status" -eq 2 ]
}

@test "short -s form without --subject is blocked" {
  _run_guard 'gh pr merge 470 -s'
  [ "$status" -eq 2 ]
}

@test "guard still fires on a later line of a multi-line script" {
  _run_guard 'set -euo pipefail
gh pr merge 470 -R es6kr/skills --squash'
  [ "$status" -eq 2 ]
}

@test "guard still fires through a timeout wrapper" {
  _run_guard 'timeout 300 gh pr merge 470 --squash'
  [ "$status" -eq 2 ]
}

@test "guard still fires when the merge follows && " {
  _run_guard 'git fetch origin && gh pr merge 470 --squash'
  [ "$status" -eq 2 ]
}

# --- true negatives (must be allowed) --------------------------------------

@test "well-formed squash subject with (#N) suffix is allowed" {
  _run_guard 'gh pr merge 470 -R es6kr/skills --squash --subject "fix(hook-kit): stop matching heredoc data (#470)"'
  [ "$status" -eq 0 ]
}

@test "line-continued squash merge with a valid subject is allowed" {
  _run_guard 'gh pr merge 470 --squash \
  --subject "fix(hook-kit): stop matching heredoc data (#470)"'
  [ "$status" -eq 0 ]
}

@test "REGRESSION: merge text inside a quoted heredoc body is not a merge call" {
  _run_guard "python3 - <<'PY'
fixture = 'gh pr merge 470 --squash'
print(fixture)
PY"
  [ "$status" -eq 0 ]
}

@test "REGRESSION: merge text inside an unquoted heredoc body is not a merge call" {
  _run_guard 'cat > /tmp/fixture.txt <<EOF
gh pr merge 470 --squash
EOF'
  [ "$status" -eq 0 ]
}

@test "REGRESSION: heredoc fixture text does not shadow surrounding real commands" {
  _run_guard "python3 - <<'PY'
cases = [
    'gh pr merge 123 --squash --subject no-suffix-here',
    'gh pr merge 123 -s',
]
for case in cases:
    print(case)
PY"
  [ "$status" -eq 0 ]
}

@test "REGRESSION: merge text inside a shell string literal is not a merge call" {
  _run_guard 'echo "gh pr merge 470 --squash"'
  [ "$status" -eq 0 ]
}

@test "REGRESSION: merge text in a trailing comment is not a merge call" {
  _run_guard 'git status --short # gh pr merge 470 --squash'
  [ "$status" -eq 0 ]
}

@test "REGRESSION: an unrelated -s flag elsewhere does not arm the squash branch" {
  _run_guard 'curl -s https://example.com && gh pr merge 470 --merge --subject "chore: merge (#470)"'
  [ "$status" -eq 0 ]
}

@test "non-Bash tool input is ignored" {
  run bash "$GUARD" <<'EOF'
{"tool_name":"Edit","tool_input":{"command":"gh pr merge 470 --squash"}}
EOF
  [ "$status" -eq 0 ]
}

@test "unbalanced quotes fail open rather than block" {
  _run_guard 'gh pr merge 470 --squash --subject "unterminated'
  [ "$status" -eq 0 ]
}
