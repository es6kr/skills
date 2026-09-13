#!/usr/bin/env bash
# PreToolUse:Bash — a shell variable assigned and then dereferenced inside a
# `wsl -- bash -c` payload.
#
# The failure is deterministic and quiet: the variable reference resolves to an
# empty string by the time the payload runs, so the command silently loses an
# argument instead of erroring on the variable. The observed shape was
#
#   wsl -- bash -c 'S=~/skills/es6kr/scripts/qdrant-store-chunk.py; python $S --id ...'
#
# which ran as `python --id ...` — python then rejected `--id` as its own unknown
# option, an error message that points nowhere near the actual cause. Both
# `S=~/...` and `S="$HOME/..."` failed the same way.
#
# failed-attempts.md class `wsl-bash-c-var-assignment-and-tmp-non-persistence`
# reached count=3 / status=hook-pending. Documented memory did not stop the
# third recurrence, which is the argument for a gate rather than another note.
#
# Scope is deliberately narrow — it fires only when BOTH halves are inside the
# payload:
#   1. an explicit `NAME=` assignment at a statement boundary, and
#   2. a later `$NAME` / `${NAME}` reference to that same name.
# A payload that only *reads* an outer variable (`wsl -- bash -c "cd $WT && …"`,
# the working pattern, where $WT is expanded Windows-side before WSL is reached)
# has no in-payload assignment and does not fire. A `for f in …; do … $f` loop
# assigns through `for`, not `NAME=`, and does not fire either.
#
# Bypass: ALLOW_WSL_VAR_PAYLOAD=1 as a command prefix.

set -uo pipefail

if [ "${1:-}" = "--test" ]; then
  PASS=0; FAIL=0; FAILED_NAMES=()
  test_case() {
    local name="$1" expected="$2" cmd="$3" actual
    set +e
    printf '%s' "$(jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}')" | "$0" >/dev/null 2>&1
    actual=$?
    set -e
    if [ "$actual" = "$expected" ]; then
      echo "  PASS: $name"; PASS=$((PASS+1))
    else
      echo "  FAIL: $name (expected=$expected got=$actual)"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$name")
    fi
  }

  echo "=== Positive fixtures (should block, exit 2) ==="
  test_case "assign then deref, single-quoted payload" 2 \
    "wsl -- bash -c 'S=~/scripts/store.py; python \$S --id 1'"
  test_case "assign then deref, double-quoted payload" 2 \
    'wsl -- bash -c "OUT=/tmp/x.json; jq . ${OUT}"'
  test_case "assign then deref with bash -lc" 2 \
    "wsl -- bash -lc 'P=/mnt/c/tmp; ls \$P'"

  echo ""
  echo "=== Negative fixtures (should allow, exit 0) ==="
  test_case "outer variable only, no in-payload assignment" 0 \
    'wsl -- bash -c "cd /mnt/c/repo && uv run python -m pytest -q"'
  test_case "for-loop variable is not a NAME= assignment" 0 \
    "wsl -- bash -c 'for f in *.md; do echo \$f; done'"
  test_case "assignment with no later reference" 0 \
    "wsl -- bash -c 'LC_ALL=C.UTF-8 python3 script.py'"
  test_case "reference with no assignment of that name" 0 \
    "wsl -- bash -c 'echo \$HOME && ls /tmp'"
  test_case "plain bash -c, not routed through wsl" 0 \
    "bash -c 'S=/tmp/x; cat \$S'"
  test_case "literal path, the recommended form" 0 \
    "wsl -- bash -c 'python3 /mnt/c/scripts/store.py --id 1'"
  test_case "assigned and referenced names differ" 0 \
    "wsl -- bash -c 'A=1; echo \$B'"
  test_case "outer assignment before the wsl call, referenced inside payload" 0     'WT=/mnt/c/repo/.worktrees/x
wsl -- bash -c "cd $WT && bats tests/"'
  test_case "outer assignment, payload also has its own unrelated env prefix" 0     'WT=/mnt/c/repo
wsl -- bash -c "cd $WT && LC_ALL=C.UTF-8 python3 x.py"'

  test_case "explicit bypass prefix" 0 \
    "ALLOW_WSL_VAR_PAYLOAD=1 wsl -- bash -c 'S=/tmp/x; cat \$S'"

  echo ""
  echo "PASS=$PASS FAIL=$FAIL"
  if [ "$FAIL" -gt 0 ]; then printf 'failed: %s\n' "${FAILED_NAMES[@]}"; exit 1; fi
  exit 0
fi

INPUT=$(cat)

# Accept both harness payload shapes (Claude Code / Antigravity), as
# block-write-file-overwrite.sh does — a hook that reads only one shape silently
# never fires on the other.
COMMAND=$(printf '%s' "$INPUT" | jq -r '
  (.tool_input.command // .toolCall.args.command // empty)
' 2>/dev/null)
TOOL=$(printf '%s' "$INPUT" | jq -r '(.tool_name // .toolCall.name // empty)' 2>/dev/null)

[ -n "$COMMAND" ] || exit 0
case "$TOOL" in Bash|bash|"") : ;; *) exit 0 ;; esac

# Explicit opt-out
case "$COMMAND" in *ALLOW_WSL_VAR_PAYLOAD=1*) exit 0 ;; esac

# Only WSL-routed bash payloads
printf '%s' "$COMMAND" | grep -qE 'wsl( +[^ ]+)* +-- +bash +-l?c' || exit 0

# The payload is whatever follows `bash -c` / `bash -lc`, taken ONLY from the
# line that actually carries the wsl invocation. sed is line-oriented, so
# stripping the prefix across the whole command lets an unrelated earlier line
# survive into PAYLOAD — and the common working shape
#
#   WT=/mnt/c/repo/.worktrees/x
#   wsl -- bash -c "cd $WT && bats tests/"
#
# would then look like an in-payload assignment plus a dereference and get
# blocked, which is precisely the pattern this hook must not touch.
PAYLOAD=$(printf '%s' "$COMMAND"   | grep -E 'wsl( +[^ ]+)* +-- +bash +-l?c'   | sed -E 's/^.*bash +-l?c +//')
[ -n "$PAYLOAD" ] || exit 0

# Names assigned at a statement boundary inside the payload: start, or after
# ; & | ( { a quote or a newline. The quote characters matter: the payload
# arrives still wrapped in the quotes the outer shell saw, so the first
# assignment sits directly behind a ' or " rather than at the string start.
# `FOO=bar cmd` (an env prefix) is caught here too, but that only matters when
# the same name is dereferenced later, which the second half requires.
ASSIGNED=$(printf '%s' "$PAYLOAD" \
  | grep -oE '(^|[;&|({'"'"'"[:space:]])[A-Za-z_][A-Za-z0-9_]*=' \
  | grep -oE '[A-Za-z_][A-Za-z0-9_]*=' \
  | sed 's/=$//' | sort -u)
[ -n "$ASSIGNED" ] || exit 0

HIT=""
for name in $ASSIGNED; do
  if printf '%s' "$PAYLOAD" | grep -qE '\$(\{)?'"$name"'([^A-Za-z0-9_]|\}|$)'; then
    HIT="$name"
    break
  fi
done
[ -n "$HIT" ] || exit 0

cat >&2 <<EOF
[hook:block-wsl-var-payload] BLOCKED (exit 2)

A shell variable is assigned and then dereferenced inside a \`wsl -- bash -c\`
payload: \$$HIT

This fails quietly. By the time the payload runs, the reference resolves to an
empty string, so the command loses an argument rather than reporting an unset
variable — and the error you get back points at the wrong thing. The recorded
case was:

  wsl -- bash -c 'S=~/scripts/store.py; python \$S --id 1'

which executed as \`python --id 1\`, and python's complaint about an unknown
option \`--id\` gave no hint that \$S was the problem. Single quotes did not help.

Use the literal value instead:

  wsl -- bash -c 'python3 /mnt/c/path/to/store.py --id 1'

If the value genuinely has to be computed, compute it OUTSIDE the payload and
let the outer shell interpolate it (\`wsl -- bash -c "cd \$WT && …"\`), which is
the form that works.

Related, same class: /tmp does not persist between \`wsl --\` invocations — the
distribution shuts down when idle and tmpfs is reset. Write and use a /tmp file
inside a SINGLE \`wsl -- bash -c\` call.

Deliberate exception: prefix the command with ALLOW_WSL_VAR_PAYLOAD=1.

Reference: failed-attempts.md class wsl-bash-c-var-assignment-and-tmp-non-persistence
EOF
exit 2
