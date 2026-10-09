#!/usr/bin/env bats
# Regression tests for block-cleanup-without-rag.sh's RAG-visibility detection
# — must accept the grammatically correct singular "1 chunk added" phrasing,
# not only the plural "N chunks added".
#
# Origin: failed-attempts.md class
# block-cleanup-without-rag-singular-plural-mismatch (2026-09-12, session
# 06cfcb84). The table-row regex (`.*(RAG|qdrant|chunks)`) and the bold-line
# regex (`\*\*.*(chunks added|qdrant).*\*\*`) both require the literal plural
# "chunks". When exactly 1 chunk is stored, the natural English phrasing is
# "1 chunk added" (no trailing 's'), which matches neither regex — a
# deterministic false-positive block on an already-correctly-formatted
# response, reproducible 100% of the time whenever N=1.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/cleanup/resources/block-cleanup-without-rag.sh"

_rag_call_transcript() {
  local f
  f="$(mktemp)"
  cat > "$f" <<'JSONL'
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"mcp__qdrant__qdrant-store","input":{}}]}}
JSONL
  echo "$f"
}

_run_guard() {
  local response="$1" transcript="$2"
  run bash "$GUARD" <<EOF
{"response":$(printf '%s' "$response" | jq -Rs .),"transcript_path":$(printf '%s' "$transcript" | jq -Rs .)}
EOF
}

@test "guard script exists and is executable" {
  [ -f "$GUARD" ]
}

@test "bold line with singular '1 chunk added' is accepted (allowed)" {
  local t
  t="$(_rag_call_transcript)"
  _run_guard '/cleanup run complete

**RAG store summary: 1 chunk added — session UUID a1b2c3d4-e5f6-7890-abcd-ef1234567890**
' "$t"
  rm -f "$t"
  [ "$status" -eq 0 ]
}

@test "table row with singular '1 chunk added' value cell is accepted (allowed)" {
  local t
  t="$(_rag_call_transcript)"
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| **3-C.1 RAG store** | **1 chunk added** |
' "$t"
  rm -f "$t"
  [ "$status" -eq 0 ]
}

@test "bold line with plural 'N chunks added' still accepted (regression)" {
  local t
  t="$(_rag_call_transcript)"
  _run_guard '/cleanup run complete

**RAG store summary: 5 chunks added — session UUID a1b2c3d4-e5f6-7890-abcd-ef1234567890**
' "$t"
  rm -f "$t"
  [ "$status" -eq 0 ]
}

@test "table row with plural 'N chunks added' value cell still accepted (regression)" {
  local t
  t="$(_rag_call_transcript)"
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| **3-C.1 RAG store** | **5 chunks added** |
' "$t"
  rm -f "$t"
  [ "$status" -eq 0 ]
}

@test "cleanup response with no RAG visibility row at all is still blocked (regression)" {
  local t
  t="$(_rag_call_transcript)"
  _run_guard '/cleanup run complete

Session wrapped up. All good.
' "$t"
  rm -f "$t"
  [ "$status" -eq 2 ]
}

@test "BLOCKED-labeled row mentioning qdrant/chunk only as prose justification is still blocked (regression, 4th-recurrence protection)" {
  local t
  t="$(_rag_call_transcript)"
  _run_guard '/cleanup run complete

| Step | Status |
|------|--------|
| BLOCKED | qdrant readyz 200, but 1 chunk failed to persist |
' "$t"
  rm -f "$t"
  [ "$status" -eq 2 ]
}
