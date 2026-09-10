#!/usr/bin/env bats
# Behavioral tests for block-cleanup-missing-rename.sh's /rename candidate
# validator — must require the full mandatory cleanup shape
# <model>-<topic>-<sessid8>, not merely any ASCII word after `/rename`.
#
# Origin: CodeRabbit finding on PR #465 — the prior regex accepted
# "/rename recommended" (an ASCII word, but not an executable candidate),
# because it required only "/rename" followed by 3+ ASCII characters.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/cleanup/resources/block-cleanup-missing-rename.sh"

_run_guard() {
  local response="$1"
  run bash "$GUARD" <<EOF
{"response":$(printf '%s' "$response" | jq -Rs .)}
EOF
}

@test "guard script exists and is executable" {
  [ -f "$GUARD" ]
}

@test "bare '/rename recommended' prose is rejected (blocked)" {
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| Session identity | Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890. `/rename` recommended |
'
  [ "$status" -eq 2 ]
}

@test "a proper <model>-<topic>-<sessid8> candidate is accepted (allowed)" {
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| Session identity | Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890. Run `/rename opus-vsix-release-a1b2c3d4` |
'
  [ "$status" -eq 0 ]
}

@test "a candidate missing the sessid8 suffix is rejected (blocked)" {
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| Session identity | Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890. Run `/rename opus-vsix-release` |
'
  [ "$status" -eq 2 ]
}
