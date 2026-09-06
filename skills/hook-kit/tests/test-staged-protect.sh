#!/bin/bash
# test-staged-protect.sh: Test suite for staged-protect.sh hook

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/../resources/staged-protect.sh"
TEST_ROOT="$SCRIPT_DIR/../../../../.tmp/test-staged-protect-$$"

mkdir -p "$TEST_ROOT/repo"
cd "$TEST_ROOT"

# Initialize test git repo
git -C "$TEST_ROOT/repo" init -q
echo "staged content" > "$TEST_ROOT/repo/staged.txt"
echo "unstaged content" > "$TEST_ROOT/repo/unstaged.txt"
echo "ignored content" > "$TEST_ROOT/repo/ignored.log"
echo "*.log" > "$TEST_ROOT/repo/.gitignore"

git -C "$TEST_ROOT/repo" add staged.txt .gitignore

echo "Running tests for staged-protect.sh..."

# T1: Direct edit to already-staged file -> should warn specific file is staged
OUT_T1=$(CLAUDE_TOOL_INPUT="{\"file_path\":\"$TEST_ROOT/repo/staged.txt\"}" bash "$HOOK_SCRIPT")
if echo "$OUT_T1" | grep -q "already staged"; then
  echo "✓ T1 PASS: Detected already-staged file"
else
  echo "✗ T1 FAIL: Output was: $OUT_T1"
  exit 1
fi

# T2: Edit to unrelated file when another file is staged -> should warn about repository staged changes
OUT_T2=$(CLAUDE_TOOL_INPUT="{\"file_path\":\"$TEST_ROOT/repo/unstaged.txt\"}" bash "$HOOK_SCRIPT")
if echo "$OUT_T2" | grep -q "has staged changes"; then
  echo "✓ T2 PASS: Warned on unstaged file in repo with active staging"
else
  echo "✗ T2 FAIL: Output was: $OUT_T2"
  exit 1
fi

# T3: Edit to .worktrees path -> exempt, no output
OUT_T3=$(CLAUDE_TOOL_INPUT="{\"file_path\":\"$TEST_ROOT/repo/.worktrees/branch/file.txt\"}" bash "$HOOK_SCRIPT")
if [ -z "$OUT_T3" ]; then
  echo "✓ T3 PASS: .worktrees path is exempt"
else
  echo "✗ T3 FAIL: Output was: $OUT_T3"
  exit 1
fi

# T4: Edit to gitignored path -> exempt, no output
OUT_T4=$(CLAUDE_TOOL_INPUT="{\"file_path\":\"$TEST_ROOT/repo/ignored.log\"}" bash "$HOOK_SCRIPT")
if [ -z "$OUT_T4" ]; then
  echo "✓ T4 PASS: gitignored path is exempt"
else
  echo "✗ T4 FAIL: Output was: $OUT_T4"
  exit 1
fi

# T5: Clean repo -> no output
git -C "$TEST_ROOT/repo" -c user.name="Test" -c user.email="test@example.com" commit -q -m "commit staged"
OUT_T5=$(CLAUDE_TOOL_INPUT="{\"file_path\":\"$TEST_ROOT/repo/unstaged.txt\"}" bash "$HOOK_SCRIPT")
if [ -z "$OUT_T5" ]; then
  echo "✓ T5 PASS: Clean repo produces no warning"
else
  echo "✗ T5 FAIL: Output was: $OUT_T5"
  exit 1
fi

# Cleanup
rm -rf "$TEST_ROOT"
echo "All staged-protect tests passed successfully!"
