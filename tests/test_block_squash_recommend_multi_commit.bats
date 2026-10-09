#!/usr/bin/env bats
# Behavioral tests for block-squash-recommend-multi-commit.sh — must deny an
# AskUserQuestion squash-merge option unless that same option discloses a
# verified single-commit count.
#
# Origin: failed-attempts.md class "squash-recommend-multi-commit"
# (es6kr/skills PR #417, 4 recurrences) — squash was offered as a merge
# option without first checking the PR's actual commit count via
# `gh pr view <N> --json commits`. Rule: skills-publishing.md "squash-merge
# 추천은 커밋 1개 PR에만 허용 (HARD STOP)".

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/github-flow/resources/block-squash-recommend-multi-commit.sh"

_mk_payload() {
  # $1 = option label, $2 = option description
  jq -n --arg label "$1" --arg desc "$2" '
    {tool_name:"AskUserQuestion", tool_input:{questions:[{question:"How should we merge this PR?", options:[{label:$label, description:$desc},{label:"Hold off",description:"do not merge yet"}]}]}}
  '
}

_run_guard() {
  run bash "$GUARD" <<< "$1"
}

@test "guard script exists and is executable" {
  [ -f "$GUARD" ]
}

@test "squash option with no commit-count disclosure is denied" {
  _run_guard "$(_mk_payload 'Squash and merge' 'combine all commits into one')"
  [ "$status" -eq 2 ]
}

@test "squash option disclosing commit count: 1 is allowed" {
  _run_guard "$(_mk_payload 'Squash and merge (Recommended)' 'commit count: 1 -- safe to squash')"
  [ "$status" -eq 0 ]
}

@test "squash option disclosing commit count: 3 is denied (multi-commit, must not be offered)" {
  _run_guard "$(_mk_payload 'Squash and merge' 'commit count: 3 -- combine into one commit')"
  [ "$status" -eq 2 ]
}

@test "non-squash option (merge commit) is allowed regardless of commit count" {
  _run_guard "$(_mk_payload 'Merge commit' 'preserve all 3 commits as-is')"
  [ "$status" -eq 0 ]
}

@test "case-insensitive SQUASH match is still denied without disclosure" {
  _run_guard "$(_mk_payload 'SQUASH AND MERGE' 'one-shot merge')"
  [ "$status" -eq 2 ]
}

@test "non-AskUserQuestion tool_name is ignored (allowed)" {
  run bash "$GUARD" <<< '{"tool_name":"Bash","tool_input":{"command":"echo squash"}}'
  [ "$status" -eq 0 ]
}
