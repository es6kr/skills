#!/usr/bin/env bash
# Unit tests for check-ask-bypass-keywords.sh conditional-deferral and other gates.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../resources/check-ask-bypass-keywords.sh"
[[ -f "$HOOK" ]] || { echo "Hook script not found: $HOOK" >&2; exit 1; }

FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

run_test() {
  local desc="$1"
  local assistant_text="$2"
  local ask_called="$3"
  local expected_decision="$4"

  local transcript_file="$TMPDIR/transcript.jsonl"
  
  if [ "$ask_called" = "true" ]; then
    # Assistant message with tool_use AskUserQuestion
    cat > "$transcript_file" <<EOF
{"type":"assistant","message":{"content":[{"type":"text","text":$(printf '%s' "$assistant_text" | jq -Rs .)},{"type":"tool_use","name":"AskUserQuestion"}]}}
EOF
  else
    # Assistant message with only text
    cat > "$transcript_file" <<EOF
{"type":"assistant","message":{"content":[{"type":"text","text":$(printf '%s' "$assistant_text" | jq -Rs .)}]}}
EOF
  fi

  local output
  output=$(printf '{"transcript_path":"%s"}' "$transcript_file" | bash "$HOOK" 2>/dev/null)
  local decision="pass"
  if [ -n "$output" ]; then
    decision=$(echo "$output" | jq -r '.decision // "pass"' 2>/dev/null)
  fi

  if [ "$decision" != "$expected_decision" ]; then
    echo "FAIL: $desc (expected $expected_decision, got $decision)"
    echo "  Text: $assistant_text"
    echo "  Output: $output"
    FAIL=$((FAIL + 1))
  else
    echo "PASS: $desc"
  fi
}

echo "Running tests for check-ask-bypass-keywords.sh..."

# 1. AskUserQuestion called -> should always pass
run_test "AskUserQuestion called in response" "Would you like to proceed? Let me know." true "pass"

# 2. English conditional deferral in prose without tool call -> should BLOCK
run_test "English conditional deferral: let me know" "Here is the summary. Let me know and I will proceed with the changes." false "block"
run_test "English conditional deferral: if you want" "All tests pass. If you'd like to deploy, I'll execute the script." false "block"
run_test "English conditional deferral: on your instruction" "Review completed. On your instruction I will merge the PR." false "block"

# 3. Trailing question mark -> should BLOCK
run_test "Trailing question mark" "Should we commit these changes now?" false "block"

# 4. Standard reporting without questions or deferral -> should PASS
run_test "Plain reporting output" "The task is complete. All 10 tests passed successfully." false "pass"

# 5. Korean conditional deferral via custom regex pattern (using Unicode escapes to keep repo clean)
# Mock HG_DATA_FILE.
#
# The hook resolves its locale data file as $(dirname $0)/../data/hangul-patterns.regex,
# a hardcoded path, so the mock has to live at that exact location. That makes this
# section destructive to a real operator-authored file: the previous version wrote the
# mock straight over it and then `rm -rf`'d the whole data/ directory on the way out,
# silently disarming every guard that sources it (check-ask-bypass-keywords itself
# falls back to __NEVER_MATCH__ = complete no-op) until someone re-authored the file.
# Stash any pre-existing data/ first and restore it via an EXIT trap so an early
# failure or Ctrl-C cannot leave the operator's file destroyed either.
MOCK_DATA_DIR="$SCRIPT_DIR/../data"
MOCK_DATA_STASH=""
if [ -e "$MOCK_DATA_DIR" ]; then
  MOCK_DATA_STASH="$(mktemp -d)/data"
  mv "$MOCK_DATA_DIR" "$MOCK_DATA_STASH"
fi
restore_mock_data() {
  rm -rf "$MOCK_DATA_DIR"
  if [ -n "$MOCK_DATA_STASH" ] && [ -e "$MOCK_DATA_STASH" ]; then
    mv "$MOCK_DATA_STASH" "$MOCK_DATA_DIR"
  fi
}
trap restore_mock_data EXIT
mkdir -p "$MOCK_DATA_DIR"
# Pattern encoded without direct Korean characters
KO_PATTERN="$(printf '(\uC54C\uB824\uC8FC\uC2DC\uBA74|\uC9C0\uC2DC\uD574? \uC8FC\uC2DC\uBA74|\uB9D0\uC500\uD574? \uC8FC\uC2DC\uBA74|\uC6D0\uD558\uC2DC\uBA74|\uD544\uC694\uD558\uC2DC\uBA74|\uC6D0\uD558\uC2E4 \uACBD\uC6B0|\uD544\uC694\uD560 \uACBD\uC6B0).*(\uC9C4\uD589|\uC2E4\uD589|\uC218\uD589|\uBC18\uC601|\uC791\uC5C5|\uC218\uC815|\uBC30\uD3EC|\uC801\uC6A9)\uD558(\uACA0|\uACA0\uC2B5|\u3139|\uB3C4\uB85D)')"
cat > "$MOCK_DATA_DIR/hangul-patterns.regex" <<EOF
HG_BYPASS_CONDITIONAL_DEFERRAL_PATTERN='$KO_PATTERN'
EOF

KO_TEXT_1="$(printf '\uC138\uBD80 \uAC80\uD1A0 \uACB0\uACFC\uC785\uB2C8\uB2E4. \uC54C\uB824\uC8FC\uC2DC\uBA74 \uADF8\uB300\uB85C \uC9C4\uD589\uD558\uACA0\uC2B5\uB2C8\uB2E4.')"
KO_TEXT_2="$(printf '\uD14C\uC2A4\uD128 \uACB0\uACFC \uC815\uC0C1\uC785\uB2C8\uB2E4. \uC6D0\uD558\uC2DC\uBA74 \uBC18\uC601\uD558\uB3C4\uB85D \uD558\uACA0\uC2B5\uB2C8\uB2E4.')"
KO_TEXT_3="$(printf '\uBAA8\uB4E0 \uC810\uAC80\uC774 \uB05D\uB0AC\uC2B5\uB2C8\uB2E4. \uD544\uC694\uD558\uC2DC\uBA74 \uC218\uC815\uD558\uACA0\uC2B5\uB2C8\uB2E4.')"
KO_TEXT_PASS="$(printf '\uBAA8\uB4E0 \uC791\uC5C5\uC774 \uC815\uC0C1\uC801\uC73C\uB85C \uC644\uB8CC\uB418\uC5C8\uC2B5\uB2C8\uB2E4.')"

run_test "Korean conditional deferral: let me know and I will proceed" "$KO_TEXT_1" false "block"
run_test "Korean conditional deferral: if desired I will apply" "$KO_TEXT_2" false "block"
run_test "Korean conditional deferral: if needed I will fix" "$KO_TEXT_3" false "block"
run_test "Korean plain statement: all tasks completed" "$KO_TEXT_PASS" false "pass"

restore_mock_data
trap - EXIT

if [ "$FAIL" -gt 0 ]; then
  echo "Tests finished with $FAIL failure(s)."
  exit 1
fi

echo "All check-ask-bypass-keywords tests passed!"
exit 0
