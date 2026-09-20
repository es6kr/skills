#!/usr/bin/env bash
# Regression tests for block-compound-commands.sh, covering the quote-context
# masking fix (3rd recurrence of the false-positive class — see
# failed-attempts.md "block-compound-commands.sh flags operators inside
# quoted strings"): a pipe/&&/||/2>&1/2>/dev/null sequence that appears only
# inside a quoted string (e.g. a grep -E regex alternation) is not a real
# shell operator and must not be blocked. True unquoted compound operators
# must still be blocked.
#
# Run:  bash skills/hook-kit/tests/test-block-compound-commands.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
HOOK="$(cd "$(dirname "$0")/.." && pwd)/resources/block-compound-commands.sh"
[[ -f "$HOOK" ]] || { echo "hook not found: $HOOK" >&2; exit 1; }

TMPERR="$(mktemp)"
trap 'rm -f "$TMPERR"' EXIT
FAIL=0

# Build a Bash-tool PreToolUse payload with the given command (default
# permission_mode, matching an ordinary interactive session).
mk() {
  local cmd="$1"
  python3 -c '
import json, sys
print(json.dumps({"tool_name": "Bash", "permission_mode": "default", "tool_input": {"command": sys.argv[1]}}))
' "$cmd"
}

run() { mk "$1" | bash "$HOOK" >/dev/null 2>"$TMPERR"; echo $?; }

check() { # name want_rc got_rc
  local name="$1" want="$2" got="$3"
  if [[ "$got" == "$want" ]]; then
    echo "PASS  $name (exit=$got)"
  else
    echo "FAIL  $name (exit=$got want=$want)"; echo "      stderr: $(cat "$TMPERR")"; FAIL=1
  fi
}

# --- False-positive regressions: quoted operators must NOT block ---

check "FP: pipe inside double-quoted grep -E alternation" 0 \
  "$(run 'grep -nE "P0:selfable|P1:selfable" file.md')"

check "FP: pipe inside single-quoted regex" 0 \
  "$(run "grep -E 'A|B' file.md")"

check "FP: && inside double-quoted string" 0 \
  "$(run 'echo "safe && string"')"

check "FP: || inside double-quoted string" 0 \
  "$(run 'echo "safe || string"')"

check "FP: 2>&1 inside double-quoted string" 0 \
  "$(run 'echo "redirect looks like 2>&1 here"')"

check "FP: 2>/dev/null inside double-quoted string" 0 \
  "$(run 'echo "path looks like 2>/dev/null here"')"

check "FP: escaped double-quote inside string does not end quoting early" 0 \
  "$(run 'echo "a \" b | c"')"

check "FP: multiple quoted pipes across args" 0 \
  "$(run 'jq -r ".a|.b" file.json')"

# --- True-positive regressions: real unquoted operators must still block ---

check "TP: unquoted pipe" 2 \
  "$(run 'grep foo file.txt | head -1')"

check "TP: unquoted &&" 2 \
  "$(run 'cd /tmp && ls')"

check "TP: unquoted ||" 2 \
  "$(run 'false || true')"

check "TP: unquoted 2>&1" 2 \
  "$(run 'some-cmd 2>&1')"

check "TP: unquoted 2>/dev/null" 2 \
  "$(run 'some-cmd 2>/dev/null')"

check "TP: unquoted pipe after a quoted-but-safe segment" 2 \
  "$(run 'grep -E "A|B" file.txt | head -1')"

if [[ "$FAIL" -eq 0 ]]; then
  echo "All block-compound-commands tests passed successfully!"
else
  exit 1
fi
