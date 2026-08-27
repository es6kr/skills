#!/usr/bin/env bats
# Behavioral tests for block-cleanup-without-claudify.sh's claudify/cleanup skill-call
# matcher — must recognize both bare ("claudify") and plugin-marketplace-qualified
# ("es6kr:claudify") Skill tool_use invocations.
#
# Origin: fix_plan.md L1302 — a 2026-08-22 cleanup that genuinely called
# Skill("es6kr:claudify", "improve"/"persist") was still blocked as missing, because
# the matcher only recognized the bare "skill":"claudify" key-value pair. Every
# plugin-routed invocation carries a "<marketplace>:<skill>" prefix, so this recurs
# on every cleanup run in a plugin-installed environment.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/cleanup/resources/block-cleanup-without-claudify.sh"

setup() {
  TESTDIR="$BATS_TEST_TMPDIR/work"
  mkdir -p "$TESTDIR"
}

# Build a synthetic transcript JSONL: a genuine /cleanup slash-command anchor line
# (Gate B), followed by one tool_use line per given skill-call body.
_make_transcript() {
  local path="$TESTDIR/transcript.jsonl"
  {
    echo '{"type":"user","message":{"content":"<command-name>/cleanup</command-name>"}}'
    for line in "$@"; do
      echo "$line"
    done
  } > "$path"
  echo "$path"
}

_run_guard() {
  local transcript="$1"
  run bash "$GUARD" <<EOF
{"transcript_path":$(printf '%s' "$transcript" | jq -Rs .)}
EOF
}

@test "guard script exists and is executable" {
  [[ -x "$GUARD" ]]
}

@test "bare skill names (cleanup + claudify improve + persist) pass" {
  local t
  t=$(_make_transcript \
    '{"type":"tool_use","input":{"skill":"cleanup"}}' \
    '{"type":"tool_use","input":{"skill":"claudify","args":"improve"}}' \
    '{"type":"tool_use","input":{"skill":"claudify","args":"persist"}}')
  _run_guard "$t"
  [[ "$status" -eq 0 ]]
  [[ "$output" != *'"decision"'* ]]
}

@test "plugin-prefixed skill names (es6kr:cleanup + es6kr:claudify improve + persist) pass" {
  local t
  t=$(_make_transcript \
    '{"type":"tool_use","input":{"skill":"es6kr:cleanup"}}' \
    '{"type":"tool_use","input":{"skill":"es6kr:claudify","args":"improve"}}' \
    '{"type":"tool_use","input":{"skill":"es6kr:claudify","args":"persist"}}')
  _run_guard "$t"
  [[ "$status" -eq 0 ]]
  [[ "$output" != *'"decision"'* ]]
}

@test "missing claudify persist (bare) is blocked" {
  local t
  t=$(_make_transcript \
    '{"type":"tool_use","input":{"skill":"cleanup"}}' \
    '{"type":"tool_use","input":{"skill":"claudify","args":"improve"}}')
  _run_guard "$t"
  [[ "$status" -eq 0 ]]
  [[ "$output" =~ \"decision\":[[:space:]]*\"block\" ]]
  [[ "$output" == *'persist'* ]]
}

@test "missing claudify entirely (prefixed cleanup only) is blocked" {
  local t
  t=$(_make_transcript \
    '{"type":"tool_use","input":{"skill":"es6kr:cleanup"}}')
  _run_guard "$t"
  [[ "$status" -eq 0 ]]
  [[ "$output" =~ \"decision\":[[:space:]]*\"block\" ]]
  [[ "$output" == *'claudify'* ]]
}

@test "missing cleanup anchor call (prefixed claudify only) is blocked" {
  local t
  t=$(_make_transcript \
    '{"type":"tool_use","input":{"skill":"es6kr:claudify","args":"improve"}}' \
    '{"type":"tool_use","input":{"skill":"es6kr:claudify","args":"persist"}}')
  _run_guard "$t"
  [[ "$status" -eq 0 ]]
  [[ "$output" =~ \"decision\":[[:space:]]*\"block\" ]]
  [[ "$output" == *'cleanup'* ]]
}
