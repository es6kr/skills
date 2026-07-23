#!/usr/bin/env bash
# e2e-expect-guard.sh — PreToolUse:Edit guard
# Warns when waitForURL/toContain assertion values in E2E spec files appear to be guesses rather than 1st-party verified values.
# Exit codes: 0 = allow (warn only), no hard block (informational)

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"

# Extract file_path from Edit tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Only target E2E spec files (.spec.ts, .test.ts in e2e/)
case "$FILE_PATH" in
  *e2e*.spec.ts|*e2e*.test.ts) ;;
  *) exit 0 ;;
esac

# Detect waitForURL or expect(...).toContain patterns in new_string
NEW_STRING=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty' 2>/dev/null)
[ -z "$NEW_STRING" ] && exit 0

if echo "$NEW_STRING" | grep -qE 'waitForURL|toContain|toMatch|toHaveURL'; then
  # Print warning message (no block — informational only)
  echo "⚠️ [e2e-expect-guard] E2E assertion value (waitForURL/toContain) modification detected."
  echo "  → Did you verify the actual destination URL from CI logs or a Playwright trace?"
  echo "  → Do not use guessed patterns (e.g., OR combinations like /sign-in|/if/flow/)."
  echo "  → Primary source: gh run view <run-id> --log-failed | grep 'current URL'"
  echo ""
  echo "  Reference: failed-attempts.md 'Deleting E2E tests in response to test failure' (2026-05-12, 2 recurrences)"
fi

exit 0
