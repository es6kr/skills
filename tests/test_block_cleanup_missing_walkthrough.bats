#!/usr/bin/env bats
# Behavioral tests for block-cleanup-missing-walkthrough.sh — a cleanup/
# session-end completion report must be blocked unless some Write/Edit
# tool_use in this session's transcript targeted a walkthrough-named file.
#
# Origin: failed-attempts.md "cleanup-report-omitted-walkthrough-artifact",
# 10th recurrence — a prose-only fix (run.md's mandatory-rows table) never
# stopped the omission because nothing mechanically checked for it, unlike
# the sibling Session-identity/rename row which already had
# block-cleanup-missing-rename.sh as a backstop.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/cleanup/resources/block-cleanup-missing-walkthrough.sh"

setup() {
  TRANSCRIPT="$(mktemp)"
}

teardown() {
  rm -f "$TRANSCRIPT"
}

_run_guard() {
  local response="$1"
  run bash "$GUARD" <<EOF
{"response":$(printf '%s' "$response" | jq -Rs .),"transcript_path":$(printf '%s' "$TRANSCRIPT" | jq -Rs .)}
EOF
}

@test "guard script exists and is executable" {
  [ -f "$GUARD" ]
}

@test "cleanup-completion report with no walkthrough write anywhere in transcript is blocked" {
  echo '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/repo/fix_plan.md"}}]}}' > "$TRANSCRIPT"
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| Session identity | Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890. Run `/rename opus-vsix-release-a1b2c3d4` |
| 3-C.1 RAG Store | 11 chunks added |
'
  [ "$status" -eq 2 ]
}

@test "cleanup-completion report WITH a walkthrough write in transcript is allowed" {
  echo '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","input":{"file_path":"/repo/.agents/docs/generated/walkthrough-topic-a1b2c3d4.md"}}]}}' > "$TRANSCRIPT"
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| Session identity | Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890. Run `/rename opus-vsix-release-a1b2c3d4` |
'
  [ "$status" -eq 0 ]
}

@test "walkthrough write path match is case-insensitive" {
  echo '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","input":{"filePath":"/repo/brain/abc/WALKTHROUGH.md"}}]}}' > "$TRANSCRIPT"
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
'
  [ "$status" -eq 0 ]
}

@test "non-cleanup response is a no-op regardless of transcript content" {
  echo '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/repo/fix_plan.md"}}]}}' > "$TRANSCRIPT"
  _run_guard 'Sure, I fixed the typo in README.md.'
  [ "$status" -eq 0 ]
}
