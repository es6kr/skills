#!/usr/bin/env bash
# Tests for check-rebase-conflict-residue.sh.
#
# Regression guard for class=rebase-conflict-residue-in-commit-message-leak.
# Detects when 'git rebase --continue' completes leaving git's auto-generated
# '± Conflicts:' / '# Conflicts:' block uncleaned in the commit message.
#
# Run:  bash skills/hook-kit/tests/test-check-rebase-conflict-residue.sh
# Exit: 0 = all pass, 1 = any fail.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GUARD_SH="$SCRIPT_DIR/../resources/check-rebase-conflict-residue.sh"

FAIL=0
PASS=0

check() {
  local label="$1" expected_rc="$2" actual_rc="$3"
  if [[ "$expected_rc" -eq "$actual_rc" ]]; then
    PASS=$((PASS + 1))
    printf 'PASS  %s (rc=%d)\n' "$label" "$actual_rc"
  else
    FAIL=$((FAIL + 1))
    printf 'FAIL  %s: expected rc=%d, got rc=%d\n' "$label" "$expected_rc" "$actual_rc" >&2
  fi
}

# Ensure guard script exists as test target
if [[ ! -f "$GUARD_SH" ]]; then
  echo "FAIL: guard script does not exist: $GUARD_SH" >&2
  echo "Result: 0 passed, 1 failed"
  exit 1
fi

TMP_REPO="$(mktemp -d)"
trap 'rm -rf "$TMP_REPO"' EXIT

# Initialize a dummy git repo for testing commit message checks
git -C "$TMP_REPO" init -q -b main
git -C "$TMP_REPO" config user.email "test@example.com"
git -C "$TMP_REPO" config user.name "Test User"

# Test 1: Non-Bash tool call is ignored (rc=0)
payload='{"tool_name": "Read", "tool_input": {"path": "foo"}}'
out="$(printf '%s' "$payload" | (cd "$TMP_REPO" && bash "$GUARD_SH" 2>&1))"
check "non-Bash tool call is ignored" 0 $?

# Test 2: Unrelated Bash command is ignored (rc=0)
payload='{"tool_name": "Bash", "tool_input": {"command": "git status"}}'
out="$(printf '%s' "$payload" | (cd "$TMP_REPO" && bash "$GUARD_SH" 2>&1))"
check "unrelated git command is ignored" 0 $?

# Test 3: Echo mentioning rebase --continue is ignored (rc=0)
payload='{"tool_name": "Bash", "tool_input": {"command": "echo \"git rebase --continue later\""}}'
out="$(printf '%s' "$payload" | (cd "$TMP_REPO" && bash "$GUARD_SH" 2>&1))"
check "echo mentioning rebase --continue is ignored" 0 $?

# Test 4: rebase --continue with clean commit passes (rc=0)
(
  cd "$TMP_REPO"
  echo "one" > f.txt
  git add f.txt
  git commit -q -m "feat: clean commit without conflict residue"
)
payload='{"tool_name": "Bash", "tool_input": {"command": "git rebase --continue"}}'
out="$(printf '%s' "$payload" | (cd "$TMP_REPO" && bash "$GUARD_SH" 2>&1))"
check "rebase --continue with clean commit passes" 0 $?

# Test 5: rebase --continue with '± Conflicts:' residue blocks (rc=2)
(
  cd "$TMP_REPO"
  echo "two" >> f.txt
  git add f.txt
  git commit -q -m "fix: some fix

± Conflicts:
±	skills/hook-kit/resources/foo.sh"
)
payload='{"tool_name": "Bash", "tool_input": {"command": "git rebase --continue"}}'
out="$(printf '%s' "$payload" | (cd "$TMP_REPO" && bash "$GUARD_SH" 2>&1))"
rc=$?
check "rebase --continue with '± Conflicts:' residue blocks" 2 $rc

# Test 6: GIT_EDITOR=true prefix with '# Conflicts:' residue blocks (rc=2)
(
  cd "$TMP_REPO"
  echo "three" >> f.txt
  git add f.txt
  git commit -q -m "chore: another commit

# Conflicts:
#	hooks/hooks.json"
)
payload='{"tool_name": "Bash", "tool_input": {"command": "GIT_EDITOR=true git rebase --continue"}}'
out="$(printf '%s' "$payload" | (cd "$TMP_REPO" && bash "$GUARD_SH" 2>&1))"
rc=$?
check "GIT_EDITOR=true rebase --continue with '# Conflicts:' residue blocks" 2 $rc

# Test 7: Compound command with rebase --continue and conflict residue blocks (rc=2)
payload='{"tool_name": "Bash", "tool_input": {"command": "git add -A && git rebase --continue"}}'
out="$(printf '%s' "$payload" | (cd "$TMP_REPO" && bash "$GUARD_SH" 2>&1))"
rc=$?
check "compound command with rebase --continue blocks on residue" 2 $rc

echo ""
echo "Result: $PASS_COUNT passed, $FAIL_COUNT failed" 2>/dev/null || echo "Result: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
