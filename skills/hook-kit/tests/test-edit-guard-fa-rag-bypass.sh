#!/bin/bash
# test-edit-guard-fa-rag-bypass.sh: Test suite for edit-guard.sh's
# check_fa_edit_without_rag_search — specifically the documented
# 'fix-rag-search-skipped' bypass token, which the function's own error
# message promises but (as of the bug this test guards against) never
# actually checked.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/../resources/edit-guard.sh"
TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/test-edit-guard-fa-rag-XXXXXX")
trap 'rm -rf "$TEST_ROOT"' EXIT

FA_FILE="$TEST_ROOT/data/failed-attempts.md"
mkdir -p "$(dirname "$FA_FILE")"
touch "$FA_FILE"

# Empty transcript — 0 RAG calls, regardless of medium (MCP find tool or
# qdrant-search.py/qdrant-import.py Bash command).
TRANSCRIPT="$TEST_ROOT/transcript.jsonl"
: > "$TRANSCRIPT"

echo "Running tests for edit-guard.sh check_fa_edit_without_rag_search..."

# T1: new FA section, no RAG calls this session, NO bypass token -> denied (exit 2)
PAYLOAD_T1=$(jq -n --arg fp "$FA_FILE" --arg tp "$TRANSCRIPT" \
  '{tool_name:"Edit", tool_input:{file_path:$fp, new_string:"## New mistake class (2026-10-09, 1st occurrence)\n\n### Problem\n- something"}, transcript_path:$tp}')
set +e
OUT_T1=$(echo "$PAYLOAD_T1" | bash "$HOOK_SCRIPT" 2>&1)
RC_T1=$?
set -e
if [ "$RC_T1" -eq 2 ] && echo "$OUT_T1" | grep -q "DENIED"; then
  echo "✓ T1 PASS: denied without bypass token and without RAG calls"
else
  echo "✗ T1 FAIL: rc=$RC_T1 output was: $OUT_T1"
  exit 1
fi

# T2: new FA section, no RAG calls this session, WITH bypass token -> allowed (exit 0)
PAYLOAD_T2=$(jq -n --arg fp "$FA_FILE" --arg tp "$TRANSCRIPT" \
  '{tool_name:"Edit", tool_input:{file_path:$fp, new_string:"## New mistake class (2026-10-09, 1st occurrence)\n\nfix-rag-search-skipped — pattern verified genuinely new via grep.\n\n### Problem\n- something"}, transcript_path:$tp}')
set +e
OUT_T2=$(echo "$PAYLOAD_T2" | bash "$HOOK_SCRIPT" 2>&1)
RC_T2=$?
set -e
if [ "$RC_T2" -eq 0 ]; then
  echo "✓ T2 PASS: bypass token allows the edit through without a RAG call"
else
  echo "✗ T2 FAIL: rc=$RC_T2 output was: $OUT_T2"
  exit 1
fi

echo "All edit-guard.sh FA-RAG-bypass tests passed successfully!"
