#!/usr/bin/env bash
# Behavioral tests for block-browser-auth-without-skill.sh.
#
# Exit: 0 = all pass, 1 = any fail.

set -u
HOOK_SH="$(cd "$(dirname "$0")/.." && pwd)/resources/block-browser-auth-without-skill.sh"
[[ -f "$HOOK_SH" ]] || { echo "hook not found: $HOOK_SH" >&2; exit 1; }

FAIL=0
PASS=0

run_case() {
  local label="$1"
  local expected_exit="$2"
  local tool_name="$3"
  local tool_url="${4:-}"
  local transcript_content="${5:-}"

  local tmpdir
  tmpdir="$(mktemp -d)"
  local transcript_file="$tmpdir/transcript.jsonl"
  touch "$transcript_file"
  if [[ -n "$transcript_content" ]]; then
    printf '%s\n' "$transcript_content" > "$transcript_file"
  fi

  local payload
  if [[ -n "$tool_url" ]]; then
    payload="$(jq -n \
      --arg tn "$tool_name" \
      --arg tp "$transcript_file" \
      --arg url "$tool_url" \
      '{tool_name: $tn, transcript_path: $tp, tool_input: {url: $url}}')"
  else
    payload="$(jq -n \
      --arg tn "$tool_name" \
      --arg tp "$transcript_file" \
      '{tool_name: $tn, transcript_path: $tp, tool_input: {}}')"
  fi

  set +e
  printf '%s' "$payload" | bash "$HOOK_SH" >/dev/null 2>&1
  local got_exit=$?
  set -e

  rm -rf "$tmpdir"

  if [[ "$got_exit" -eq "$expected_exit" ]]; then
    echo "  PASS: $label (exit $got_exit)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (expected $expected_exit, got $got_exit)"
    FAIL=$((FAIL + 1))
  fi
}

echo "Running block-browser-auth-without-skill.sh tests..."

# 1. Direct navigate to auth URL without skill -> exit 2
run_case "navigate to github.com/login without skill blocks" 2 \
  "browser_navigate" "https://github.com/login" ""

# 2. Direct navigate to auth URL with skill in transcript -> exit 0
run_case "navigate to github.com/login with skill allows" 0 \
  "browser_navigate" "https://github.com/login" \
  '{"type":"tool_use","name":"Skill","input":{"skill":"web-browser"}}'

# 3. Direct navigate to benign URL -> exit 0
run_case "navigate to benign URL allows" 0 \
  "browser_navigate" "https://example.com" ""

# 4. browser_click on already-open auth page -> exit 2
run_case "click on already-open auth page blocks" 2 \
  "browser_click" "" \
  '{"type":"tool_use","name":"browser_navigate","input":{"url":"https://github.com/login"}}'

# 5. browser_evaluate on already-open auth page -> exit 2
run_case "browser_evaluate on already-open auth page blocks" 2 \
  "browser_evaluate" "" \
  '{"type":"tool_use","name":"browser_navigate","input":{"url":"https://accounts.google.com"}}'

# 6. browser_click on auth page with skill in transcript -> exit 0
run_case "click on auth page with skill allows" 0 \
  "browser_click" "" \
  '{"type":"tool_use","name":"Skill","input":{"skill":"web-browser"}}
{"type":"tool_use","name":"browser_navigate","input":{"url":"https://github.com/login"}}'

# 7. browser_click without any auth URL in transcript -> exit 0
run_case "click on benign page allows" 0 \
  "browser_click" "" \
  '{"type":"tool_use","name":"browser_navigate","input":{"url":"https://example.com"}}'

# 8. Prose mention of auth URL (not inside "url": "...") -> exit 0 (FP prevention)
run_case "chat prose mention of auth URL does not block click" 0 \
  "browser_click" "" \
  '{"type":"text","content":"Please check https://github.com/login for credentials"}'

echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
