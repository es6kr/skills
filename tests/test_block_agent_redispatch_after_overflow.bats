#!/usr/bin/env bats
# Behavioral tests for block-agent-redispatch-after-overflow.js (PreToolUse:Agent gate).
#
# The guard exists because "Agent terminated early due to an API error: Prompt is too long"
# has recurred 10 times (failed-attempts class code-reviewer-dispatch-model-policy-not-consulted).
# The binding constraint is the subagent's own context budget — NOT the caller's prompt length,
# NOT the model tier, NOT the tool-schema size. So once one dispatch in a session has overflowed,
# another dispatch of the same shape is a known-deterministic waste: the caller must move down
# the consolidate/internal.md escalation ladder (rung 2 / rung 3) instead of re-dispatching.
#
# Runs fully offline: each test writes a synthetic transcript JSONL and feeds the guard a
# PreToolUse payload on stdin. No network, no git, no real Agent spawn.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/hook-kit/resources/block-agent-redispatch-after-overflow.js"

setup() {
  TESTDIR="$BATS_TEST_TMPDIR/work"
  mkdir -p "$TESTDIR"
  TRANSCRIPT="$TESTDIR/transcript.jsonl"
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX
}

# a transcript with no overflow evidence
_clean_transcript() {
  : > "$TRANSCRIPT"
  printf '%s\n' '{"message":{"role":"user","content":"do the thing"}}' >> "$TRANSCRIPT"
  printf '%s\n' '{"message":{"role":"assistant","content":[{"type":"text","text":"working"}]}}' >> "$TRANSCRIPT"
}

# a transcript carrying one prior context-overflow failure
_overflow_transcript() {
  _clean_transcript
  printf '%s\n' '{"message":{"role":"user","content":[{"type":"tool_result","content":"Agent terminated early due to an API error: Prompt is too long"}]}}' >> "$TRANSCRIPT"
}

# emit a PreToolUse payload for an Agent spawn with the given prompt
_payload() {
  local prompt="$1"
  python3 - "$prompt" "$TRANSCRIPT" <<'PY'
import json, sys
print(json.dumps({
    "tool_name": "Agent",
    "tool_input": {"subagent_type": "general-purpose", "prompt": sys.argv[1]},
    "transcript_path": sys.argv[2],
}))
PY
}

@test "allows an Agent spawn when the transcript has no prior overflow" {
  _clean_transcript
  run bash -c "$(_payload 'review this diff') | node '$GUARD'"
  [ "$status" -eq 0 ]
}

@test "denies a second Agent spawn after one prior Prompt-is-too-long failure" {
  _overflow_transcript
  run bash -c "$(_payload 'review this diff') | node '$GUARD'"
  [ "$status" -eq 2 ]
  [[ "$output" == *"escalation ladder"* ]]
}

@test "deny message names the closed directions so they are not retried" {
  _overflow_transcript
  run bash -c "$(_payload 'review this diff') | node '$GUARD'"
  [ "$status" -eq 2 ]
  [[ "$output" == *"tier"* ]]
  [[ "$output" == *"chunking"* ]]
}

@test "allows the spawn when the prompt carries a bare rung-escalated marker" {
  _overflow_transcript
  run bash -c "$(_payload 'review this diff [rung-escalated]') | node '$GUARD'"
  [ "$status" -eq 0 ]
}

# Regression guard: the [bg-inherit-ok] marker in a sibling hook was matched as an exact
# substring, so the natural "[marker] <reason>" and "[marker: <reason>]" spellings were both
# rejected and the caller was re-blocked three times running. This marker must accept a
# trailing reason in either spelling.
@test "rung-escalated marker still works with a trailing reason" {
  _overflow_transcript
  run bash -c "$(_payload 'review [rung-escalated] rung 3 self-analysed per internal.md') | node '$GUARD'"
  [ "$status" -eq 0 ]
}

@test "rung-escalated marker still works in the label-colon-reason spelling" {
  _overflow_transcript
  run bash -c "$(_payload 'review [rung-escalated: rung 3 self-analysed]') | node '$GUARD'"
  [ "$status" -eq 0 ]
}

@test "ignores non-Agent tool calls" {
  _overflow_transcript
  local payload
  payload=$(python3 -c "
import json
print(json.dumps({'tool_name':'Bash','tool_input':{'command':'ls'},'transcript_path':'$TRANSCRIPT'}))
")
  run bash -c "printf '%s' '$payload' | node '$GUARD'"
  [ "$status" -eq 0 ]
}

@test "allows the spawn when no transcript path is supplied" {
  local payload
  payload=$(python3 -c "
import json
print(json.dumps({'tool_name':'Agent','tool_input':{'prompt':'x'}}))
")
  run bash -c "printf '%s' '$payload' | node '$GUARD'"
  [ "$status" -eq 0 ]
}
