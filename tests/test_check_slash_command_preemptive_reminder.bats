#!/usr/bin/env bats
# Regression tests for the UserPromptSubmit (preventive) branch of
# skills/hook-kit/resources/check-slash-command-skill-invoked.sh.
#
# The Stop branch (the backstop) is covered by tests/test_pr623_command_guards.py.
# This file locks down the part that lands BEFORE the model's first token: when
# the user types `/<slug>` for an installed skill, the harness injects the
# skill text as a user message, which is easy to mistake for an invocation. The
# hook must remind the model that Skill("<slug>", ...) has to be its first tool
# call, and must stay silent for native commands, paths and plain prose.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/hook-kit/resources/check-slash-command-skill-invoked.sh"

setup() {
  [ -f "$GUARD" ] || skip "guard not found: $GUARD"
  command -v jq >/dev/null || skip "jq not available"
  # Isolated HOME so skill_exists() sees only the skills this test installs.
  export HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$HOME/.claude/skills/cleanup"
}

# run_prompt <prompt text> -> runs the hook as a UserPromptSubmit event.
run_prompt() {
  jq -n --arg p "$1" '{hook_event_name: "UserPromptSubmit", prompt: $p}' | bash "$GUARD"
}

@test "reminds on a raw namespaced slash command with args" {
  run run_prompt "/es6kr:cleanup --auto"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"hookEventName": "UserPromptSubmit"'* ]]
  [[ "$output" == *'Skill(\"es6kr:cleanup\"'* ]]
  [[ "$output" == *"FIRST tool call"* ]]
}

@test "reminds on a bare slash command with no args" {
  run run_prompt "/cleanup"
  [ "$status" -eq 0 ]
  [[ "$output" == *'Skill(\"cleanup\"'* ]]
}

@test "reminds when the prompt is the expanded command-name tag" {
  run run_prompt "<command-message>cleanup</command-message><command-name>/cleanup</command-name>"
  [ "$status" -eq 0 ]
  [[ "$output" == *'Skill(\"cleanup\"'* ]]
}

@test "reminds when leading whitespace precedes the slash command" {
  run run_prompt "   /cleanup run"
  [ "$status" -eq 0 ]
  [[ "$output" == *'Skill(\"cleanup\"'* ]]
}

@test "silent for a native command that is not an installed skill" {
  run run_prompt "/compact"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "silent for an absolute path that starts like a command" {
  run run_prompt "/cleanup/notes/today.md please summarize"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "silent for plain prose that mentions a slash command" {
  run run_prompt "please run /cleanup when you are done"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "silent for an empty prompt" {
  run run_prompt ""
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "silent inside an autonomous Ralph loop" {
  RALPH_LOOP=1 run run_prompt "/cleanup --auto"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "an event without hook_event_name still takes the Stop path and passes without a transcript" {
  run bash -c "echo '{}' | bash '$GUARD'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
