#!/usr/bin/env bats
# Regression tests for the wrap-up keyword pattern in
# block-cleanup-option-below-context-gate.sh.
#
# Scope: the pattern itself, evaluated exactly the way the guard evaluates it —
# jq's `test($pattern; "i")` against an option's label+description text. Driving
# the whole guard end-to-end would require mocking the context-usage pipeline;
# what actually regressed here was the pattern, so that is what these lock down.
#
# The hazard: "retrospect" is a substring of branch names and file paths. An
# option that merely *names* `fix/retrospect-script-path` or `cleanup/retrospect.md`
# is not offering a session wrap-up, but an unanchored alternative matched it and
# denied the ask. A guard that blocks ordinary work teaches people to route
# around it, so a false positive here costs more than the miss it prevents.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/cleanup/resources/block-cleanup-option-below-context-gate.sh"

setup() {
  [ -f "$GUARD" ] || skip "guard not found: $GUARD"
  command -v jq >/dev/null || skip "jq not available"
  PATTERN="$(grep -m1 "^WRAPUP_PATTERN_EN=" "$GUARD" | sed "s/^WRAPUP_PATTERN_EN='//;s/'$//")"
  [ -n "$PATTERN" ] || skip "could not extract WRAPUP_PATTERN_EN"
}

# Returns 0 when the text matches the wrap-up pattern, 1 otherwise.
matches() {
  local out
  out="$(printf '%s' "$1" | jq -R --arg p "$PATTERN" -r 'if test($p;"i") then "y" else "n" end')"
  [ "$out" = "y" ]
}

@test "branch name containing the keyword is not a wrap-up offer" {
  ! matches "b28ff59a on branch fix/retrospect-script-path"
}

@test "file path containing the keyword is not a wrap-up offer" {
  ! matches "update the cleanup/retrospect.md topic"
}

@test "bare slug containing the keyword is not a wrap-up offer" {
  ! matches "push retrospect-script-path to origin"
}

@test "the keyword standing alone is a wrap-up offer" {
  matches "run a retrospect before ending"
}

@test "the adjectival form is still a wrap-up offer" {
  matches "session retrospective and cleanup"
}

@test "wrap-up phrasing is a wrap-up offer" {
  matches "wrap-up the session"
}

@test "the slash command is a wrap-up offer" {
  matches "/cleanup second pass"
}

@test "a path ending in cleanup is not the slash command" {
  ! matches "see skills/cleanup for details"
}
