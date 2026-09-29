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
# Runs fully offline: each test writes a synthetic transcript JSONL plus a PreToolUse payload
# file, and feeds the payload to the guard on stdin. No network, no git, no real Agent spawn.
#
# Payloads are passed by FILE REDIRECT, never interpolated into a `bash -c "..."` string.
# An earlier revision of this file did the latter; the JSON's own double quotes were eaten by
# the outer quoting, the guard saw an unparseable payload, and its fail-open path returned 0 —
# which made every ALLOW assertion pass for the wrong reason while the DENY ones failed. A
# guard that fails open cannot be tested through a channel that can silently corrupt its input.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/hook-kit/resources/block-agent-redispatch-after-overflow.js"

setup() {
  TESTDIR="$BATS_TEST_TMPDIR/work"
  mkdir -p "$TESTDIR"
  TRANSCRIPT="$TESTDIR/transcript.jsonl"
  PAYLOAD="$TESTDIR/payload.json"
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX
}

# --- transcript builders ----------------------------------------------------

_clean_transcript() {
  : > "$TRANSCRIPT"
  printf '%s\n' '{"message":{"role":"user","content":"do the thing"}}' >> "$TRANSCRIPT"
  printf '%s\n' '{"message":{"role":"assistant","content":[{"type":"text","text":"working"}]}}' >> "$TRANSCRIPT"
}

_append() { printf '%s\n' "$1" >> "$TRANSCRIPT"; }

# one prior context-overflow failure, reported the way a failed Agent spawn reports back
_overflow_transcript() {
  _clean_transcript
  _append '{"message":{"role":"user","content":[{"type":"tool_result","content":"Agent terminated early due to an API error: Prompt is too long"}]}}'
}

# --- payload builders ------------------------------------------------------

# _write_payload <prompt>  → an Agent spawn carrying that prompt
_write_payload() {
  python3 - "$1" "$TRANSCRIPT" "$PAYLOAD" <<'PY'
import json, sys
prompt, transcript, out = sys.argv[1], sys.argv[2], sys.argv[3]
with open(out, "w", encoding="utf-8") as fh:
    json.dump({
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "general-purpose", "prompt": prompt},
        "transcript_path": transcript,
    }, fh)
PY
}

_write_raw_payload() {
  printf '%s' "$1" > "$PAYLOAD"
}

_run_guard() {
  run bash -c "node '$GUARD' < '$PAYLOAD'"
}

# --- core behaviour --------------------------------------------------------

@test "allows an Agent spawn when the transcript has no prior overflow" {
  _clean_transcript
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "denies a second Agent spawn after one prior Prompt-is-too-long failure" {
  _overflow_transcript
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 2 ]
  [[ "$output" == *"escalation ladder"* ]]
}

@test "deny message names the closed directions so they are not retried" {
  _overflow_transcript
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 2 ]
  [[ "$output" == *"tier"* ]]
  [[ "$output" == *"chunking"* ]]
}

@test "counts multiple prior overflows and reports the count" {
  _overflow_transcript
  _append '{"message":{"role":"user","content":[{"type":"tool_result","content":"Agent terminated early due to an API error: Prompt is too long"}]}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 2 ]
  [[ "$output" == *"2 Agent dispatches have"* ]]
}

@test "a failing task-notification DOES block (background-agent carrier)" {
  _clean_transcript
  _append '{"message":{"role":"user","content":"<task-notification><status>failed</status><summary>Agent terminated early due to an API error: Prompt is too long</summary></task-notification>"}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 2 ]
}

# --- bypass marker ---------------------------------------------------------
# Regression guard: the [bg-inherit-ok] marker in a sibling hook was matched as an exact
# substring, so the natural "[marker] <reason>" and "[marker: <reason>]" spellings were both
# rejected and the caller was re-blocked three times running. Match the opening token only.

@test "allows the spawn when the prompt carries a bare rung-escalated marker" {
  _overflow_transcript
  _write_payload 'review this diff [rung-escalated]'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "rung-escalated marker still works with a trailing reason" {
  _overflow_transcript
  _write_payload 'review [rung-escalated] rung 3 self-analysed per internal.md'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "rung-escalated marker still works in the label-colon-reason spelling" {
  _overflow_transcript
  _write_payload 'review [rung-escalated: rung 3 self-analysed]'
  _run_guard
  [ "$status" -eq 0 ]
}

# --- scope / robustness ----------------------------------------------------

@test "ignores non-Agent tool calls" {
  _overflow_transcript
  _write_raw_payload "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"ls\"},\"transcript_path\":\"$TRANSCRIPT\"}"
  _run_guard
  [ "$status" -eq 0 ]
}

@test "allows the spawn when no transcript path is supplied" {
  _write_raw_payload '{"tool_name":"Agent","tool_input":{"prompt":"x"}}'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "allows the spawn when the transcript path does not exist" {
  _write_raw_payload '{"tool_name":"Agent","tool_input":{"prompt":"x"},"transcript_path":"/nonexistent/none.jsonl"}'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "fails open on an unparseable payload rather than wedging every spawn" {
  _overflow_transcript
  _write_raw_payload 'not json at all'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "survives a corrupted JSONL line without blocking spuriously" {
  _clean_transcript
  _append '{"message":{"role":"user","content":[{"type":"tool_result","content":"Agent terminated early due to an API error: Prompt is too long"'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}

# --- false-positive samples ------------------------------------------------
# Once a session has written the failure sentence into a commit message, a recurrence-log
# entry, or its own narration, a naive substring scan would block every later Agent spawn in
# that session. Each sample below carries the sentence in a NON-failure position and must pass.

@test "FP: assistant prose quoting the failure sentence does not block" {
  _clean_transcript
  _append '{"message":{"role":"assistant","content":[{"type":"text","text":"The dispatch failed with Agent terminated early due to an API error: Prompt is too long, so I will escalate."}]}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "FP: a user prompt quoting the failure sentence does not block" {
  _clean_transcript
  _append '{"message":{"role":"user","content":"why does Agent terminated early due to an API error: Prompt is too long keep happening?"}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "FP: a commit message carrying the sentence does not block" {
  _clean_transcript
  _append '{"message":{"role":"assistant","content":[{"type":"text","text":"git commit -m guard against Agent terminated early due to an API error: Prompt is too long"}]}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "FP: a recurrence-log tool_result about the sentence does not block" {
  _clean_transcript
  _append '{"message":{"role":"user","content":[{"type":"tool_result","content":"failed-attempts.md:354:- Agent terminated early due to an API error (Prompt is too long) 9th recurrence"}]}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "FP: an unrelated tool_result does not block" {
  _clean_transcript
  _append '{"message":{"role":"user","content":[{"type":"tool_result","content":"8 files changed, 120 insertions(+)"}]}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}

@test "FP: a task-notification for a COMPLETED agent does not block" {
  _clean_transcript
  _append '{"message":{"role":"user","content":"<task-notification><status>completed</status><summary>Agent finished the review</summary></task-notification>"}}'
  _write_payload 'review this diff'
  _run_guard
  [ "$status" -eq 0 ]
}
