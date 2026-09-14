#!/usr/bin/env bash
# Fixture-driven regression test for resolve-terminal.sh. No live Orca app needed.
set -euo pipefail
cd "$(dirname "$0")"

FIXTURE='{"ok":true,"result":{"terminals":[
 {"handle":"term_self","tabId":"TAB","leafId":"LEAF","title":"◐ me","connected":true,"writable":true,"orphaned":false,"preview":"x","worktreePath":"","branch":"","lastOutputAt":1},
 {"handle":"term_a","tabId":"TAB","leafId":"OTHER1","title":"◐ Claude Code","connected":true,"writable":true,"orphaned":false,"preview":"impl","worktreePath":"/w/a","branch":"m","lastOutputAt":2},
 {"handle":"term_b","tabId":"TAB","leafId":"OTHER2","title":"◐ Claude Code","connected":true,"writable":true,"orphaned":false,"preview":"impl","worktreePath":"/w/b","branch":"m","lastOutputAt":3},
 {"handle":"term_dead","tabId":"TAB","leafId":"OTHER3","title":"◐ Claude Code","connected":false,"writable":false,"orphaned":true,"preview":"impl","worktreePath":"","branch":"","lastOutputAt":4}
]}}'

fail=0
assert_eq() { # $1=label $2=expected $3=actual
  if [ "$2" = "$3" ]; then
    echo "PASS $1"
  else
    echo "FAIL $1: expected=[$2] actual=[$3]"
    fail=1
  fi
}

# --- Case 1: self is always excluded, dead terminal is always excluded ---
out=$(ORCA_PANE_KEY="TAB:LEAF" ORCA_TERMINAL_LIST_JSON="$FIXTURE" ./resolve-terminal.sh "Claude Code" ".")
has_self=$(printf '%s' "$out" | grep -q term_self && echo true || echo false)
has_dead=$(printf '%s' "$out" | grep -q term_dead && echo true || echo false)
count=$(printf '%s' "$out" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).count))')

assert_eq "self excluded"       "false" "$has_self"
assert_eq "dead excluded"       "false" "$has_dead"
assert_eq "two live candidates" "2"     "$count"

# --- Case 2: title/preview filters narrow to a single candidate ---
out2=$(ORCA_PANE_KEY="TAB:LEAF" ORCA_TERMINAL_LIST_JSON="$FIXTURE" ./resolve-terminal.sh "Claude Code" "^impl$")
count2=$(printf '%s' "$out2" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).count))')
assert_eq "regex on preview still returns both (same preview)" "2" "$count2"

out3=$(ORCA_PANE_KEY="TAB:LEAF" ORCA_TERMINAL_LIST_JSON="$FIXTURE" ./resolve-terminal.sh "nomatch-xyz" ".")
count3=$(printf '%s' "$out3" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).count))')
assert_eq "no title match -> zero candidates" "0" "$count3"

# --- Case 3: fail-closed when ORCA_PANE_KEY is missing ---
if (unset ORCA_PANE_KEY; ORCA_TERMINAL_LIST_JSON="$FIXTURE" ./resolve-terminal.sh "x" "y") >/dev/null 2>&1; then
  echo "FAIL no-pane-key should exit non-zero"
  fail=1
else
  echo "PASS no-pane-key fail-closed"
fi

exit $fail
