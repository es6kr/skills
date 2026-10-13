#!/usr/bin/env bats
# Behavioral tests for block-cleanup-without-rag.sh — the RAG-visibility half
# of the /cleanup completion-report gate.
#
# Focus: the transcript-fallback RESPONSE extraction path (payload carries only
# `transcript_path`, no `.response`). The two sibling guards
# (block-cleanup-missing-rename.sh / block-cleanup-missing-walkthrough.sh)
# extract ONLY the last assistant message there (`jq -rs ... | last`), while
# this guard concatenated every assistant message in the window and then piped
# the blob through `tail -100`. Both defects are false-positive generators:
#
#   A. a cleanup marker from an EARLIER turn keeps the trigger gate open, so an
#      ordinary mid-work progress message is judged as a completion report
#      (fix_plan.md: "SDD loop progress report classified as session-end");
#   B. a long completion report that DOES carry its RAG row near the top loses
#      that row to `tail -100`, so a compliant report is re-blocked
#      (fix_plan.md 2026-10-04: emitting the RAG line alone was the workaround).
#
# Origin: fix_plan.md "block-cleanup-without-rag.sh false positives" (P2:selfable,
# 5+ recurrences). Weighted toward negatives per hook-kit/add.md Step 5.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/cleanup/resources/block-cleanup-without-rag.sh"

# A RAG receiver call, so HAS_RAG_CALL=1 and the guard reaches its verdict.
# Kept FIRST in the transcript so the LAST assistant entry is always a text
# message — otherwise a last-message extraction would yield empty text and the
# guard would exit 0 for the wrong reason.
RAG_CALL='{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"python skills/qdrant/scripts/qdrant-import.py --session"}}]}}'

setup() {
  TRANSCRIPT="$(mktemp)"
}

teardown() {
  rm -f "$TRANSCRIPT"
}

# Append one assistant text message to the transcript fixture.
_add_msg() {
  printf '%s\n' "$(jq -nc --arg t "$1" '{type:"assistant",message:{content:[{type:"text",text:$t}]}}')" >> "$TRANSCRIPT"
}

# Invoke the guard with a transcript-only payload (no `.response`), forcing the
# fallback extraction path under test.
_run_guard_transcript_only() {
  run bash "$GUARD" <<EOF
{"transcript_path":$(printf '%s' "$TRANSCRIPT" | jq -Rs .)}
EOF
}

@test "guard script exists and is executable" {
  [ -f "$GUARD" ]
  [ -x "$GUARD" ]
}

# --- true positive: the behaviour that must be preserved ---------------------

@test "completion report with a RAG call but no RAG row is blocked" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg '/cleanup run complete

| Step | Result |
|------|--------|
| 1. Commit | 2 commits |
| 5. wip | 3 tasks registered |
'
  _run_guard_transcript_only
  [ "$status" -eq 2 ]
}

# --- false positive A: stale marker from an earlier turn ---------------------

@test "ordinary progress message is NOT treated as a completion report when an earlier turn mentioned /cleanup" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg 'Starting /cleanup run now — Step 0 TaskList first.'
  _add_msg 'Step 2 of the refactor is done; next I will update the adapter and re-run the suite.'
  _run_guard_transcript_only
  [ "$status" -eq 0 ]
  # Silence must be real silence, not partial or garbled JSON.
  [ -z "$output" ]
}

# --- false positive B: long compliant report loses its RAG row to truncation -

@test "long completion report carrying a RAG row near the top is allowed" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  local filler=""
  for i in $(seq 1 130); do
    filler="${filler}| step detail ${i} | done |
"
  done
  # RAG row sits at the TOP of a long table; a trailing next-actions line
  # mentions cleanup again, so the marker survives a tail-based window while
  # the compliant RAG row is cut from it.
  _add_msg "/cleanup run complete

| Step | Result |
|------|--------|
| **3-C.1 RAG Store** | **12 chunks added (receiver: qdrant-import) — session UUID a1b2c3d4-e5f6-7890-abcd-ef1234567890** |
${filler}
Next session: run /cleanup again after the release lands.
"
  _run_guard_transcript_only
  [ "$status" -eq 0 ]
}

@test "compliant report stays allowed when earlier turns also carry cleanup markers" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg 'Beginning /cleanup wrap-up — measuring context first.'
  _add_msg '/cleanup run complete

| Step | Result |
|------|--------|
| **3-C.1 RAG Store** | **7 chunks added (receiver: qdrant-import)** |
'
  _run_guard_transcript_only
  [ "$status" -eq 0 ]
}

# --- further negatives ------------------------------------------------------

@test "no RAG call + completion-report table claiming success is blocked" {
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls -la"}}]}}' > "$TRANSCRIPT"
  _add_msg '/cleanup run complete

| Step | Result |
|------|--------|
| 1. Commit | clean |
| 3. Knowledge Persist | done |
| 5. wip task registration | 2 tasks |
'
  _run_guard_transcript_only
  [ "$status" -eq 2 ]
  echo "$output" | jq -e '.reason | test("skipped")'
}

@test "no RAG call + report that honestly declares FAILED is allowed" {
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls -la"}}]}}' > "$TRANSCRIPT"
  _add_msg 'cleanup wrap-up

| Step | Result |
|------|--------|
| 1. Commit | clean |
| 3-C.1 RAG | FAILED - queued to the local pending-import queue, retry task registered |
'
  _run_guard_transcript_only
  [ "$status" -eq 0 ]
}

@test "no RAG call + mid-progress prose without a report table is allowed" {
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls -la"}}]}}' > "$TRANSCRIPT"
  _add_msg 'Starting /cleanup run - Step 0 TaskList first, then I will commit.'
  _run_guard_transcript_only
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "no RAG call + report that already carries a RAG row is allowed" {
  printf '%s\n' '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls -la"}}]}}' > "$TRANSCRIPT"
  _add_msg '/cleanup run complete

| Step | Result |
|------|--------|
| **3-C.1 RAG Store** | **0 chunks added - no receiver configured in this workspace** |
'
  _run_guard_transcript_only
  [ "$status" -eq 0 ]
}

# --- marker alignment with the sibling guards ---------------------------------

@test "session-end titled report with a RAG call but no RAG row is blocked" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg '## Session Ended

| Step | Result |
|------|--------|
| 1. Commit | 1 commit |
| 5. wip task registration | 2 tasks |
'
  _run_guard_transcript_only
  [ "$status" -eq 2 ]
}

@test "session-end report phrasing opens the trigger gate" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg 'This is the session-end report.

| Step | Result |
|------|--------|
| 1. Commit | 1 commit |
'
  _run_guard_transcript_only
  [ "$status" -eq 2 ]
}

@test "unrelated response that merely mentions qdrant is not blocked" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg 'The qdrant receiver is reachable; I will wire the importer next.'
  _run_guard_transcript_only
  [ "$status" -eq 0 ]
}

@test "RALPH_LOOP=1 passes silently even on a violating report" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg '/cleanup run complete

| Step | Result |
|------|--------|
| 1. Commit | 1 commit |
'
  RALPH_LOOP=1 run bash "$GUARD" <<EOF
{"transcript_path":$(printf '%s' "$TRANSCRIPT" | jq -Rs .)}
EOF
  [ "$status" -eq 0 ]
}

@test "explicit .response field still takes precedence over the transcript" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg 'irrelevant transcript tail'
  run bash "$GUARD" <<EOF
{"response":$(printf '%s' '/cleanup run complete

| Step | Result |
|------|--------|
| 1. Commit | 1 commit |
' | jq -Rs .),"transcript_path":$(printf '%s' "$TRANSCRIPT" | jq -Rs .)}
EOF
  [ "$status" -eq 2 ]
}

# --- trigger-gate phrasing variants (hook-kit/add.md two-part smoke test) ----
# The gate must open regardless of capitalisation; a case-sensitive marker gate
# is the silent-no-op failure mode (hook-kit: "marker gate case-sensitivity").

@test "trigger gate opens on a capitalised cleanup marker" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg 'Cleanup Run Complete

| Step | Result |
|------|--------|
| 1. Commit | 1 commit |
'
  _run_guard_transcript_only
  [ "$status" -eq 2 ]
}

@test "trigger gate opens on the cleanup wrap-up phrasing" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg 'cleanup wrap-up

| Step | Result |
|------|--------|
| 1. Commit | 1 commit |
'
  _run_guard_transcript_only
  [ "$status" -eq 2 ]
}

@test "block verdict carries the Stop-event decision schema" {
  printf '%s\n' "$RAG_CALL" > "$TRANSCRIPT"
  _add_msg '/cleanup run complete

| Step | Result |
|------|--------|
| 1. Commit | 1 commit |
'
  _run_guard_transcript_only
  [ "$status" -eq 2 ]
  echo "$output" | jq -e '.decision == "block"'
  echo "$output" | jq -e '.reason | test("chunks added")'
}
