#!/usr/bin/env bash
# Tests for check-plugin-load-failures.sh's Node counterpart
# (check-plugin-load-failures.js) — the SessionStart plugin-health advisory.
#
# Regression this guards: a plugin whose manifest name mismatches its
# registered marketplace name fails to load with zero visible symptoms in the
# session — no crash, no error, just its hooks/skills silently absent. The
# hook exists so that state is surfaced at every session start instead of
# requiring someone to run `claude plugin list` by hand.
#
# `claude` is stubbed via PATH so the test is deterministic/offline: the stub
# emits a canned `claude plugin list` payload from $STUB_PLUGIN_LIST.
#
# Run:  bash skills/hook-kit/tests/test-check-plugin-load-failures.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
HOOK="$(cd "$(dirname "$0")/../resources" && pwd)/check-plugin-load-failures.js"
[[ -f "$HOOK" ]] || { echo "hook not found: $HOOK" >&2; exit 1; }

STUBDIR="$(mktemp -d)"
cat > "$STUBDIR/claude" <<'EOF'
#!/usr/bin/env bash
# minimal claude stub: emits $STUB_PLUGIN_LIST for `plugin list`, ignores the rest
printf '%s\n' "${STUB_PLUGIN_LIST:-}"
EOF
chmod +x "$STUBDIR/claude"
trap 'rm -rf "$STUBDIR"' EXIT
FAIL=0

run() { # $1 = STUB_PLUGIN_LIST
  STUB_PLUGIN_LIST="$1" PATH="$STUBDIR:$PATH" node "$HOOK" SessionStart </dev/null
}
check_empty() { # name output
  if [[ -z "$2" ]]; then echo "PASS  $1"; else echo "FAIL  $1 (expected no output, got: $2)"; FAIL=1; fi
}
check_contains() { # name output needle
  if [[ "$2" == *"$3"* ]]; then echo "PASS  $1"; else echo "FAIL  $1 (expected to contain: $3, got: $2)"; FAIL=1; fi
}

ALL_HEALTHY='Installed plugins:

  ❯ ask-user@dgs
    Version: 0.1.0
    Scope: user
    Status: ✔ enabled

  ❯ es6kr@es6kr-skills
    Version: 0.1.1
    Scope: user
    Status: ✔ enabled'

OUT_HEALTHY="$(run "$ALL_HEALTHY")"
check_empty "all-healthy plugin list produces no output" "$OUT_HEALTHY"

ONE_FAILED='Installed plugins:

  ❯ ask-user@dgs-plugins
    Version: unknown
    Scope: user
    Status: ✖ failed to load — Marketplace dgs-plugins not found

  ❯ es6kr@es6kr-skills
    Version: 0.1.1
    Scope: user
    Status: ✔ enabled'

OUT_ONE="$(run "$ONE_FAILED")"
check_contains "one failure surfaces plugin name in additionalContext" "$OUT_ONE" "ask-user@dgs-plugins"
check_contains "one failure surfaces the failure count" "$OUT_ONE" "1 plugin(s) failed to load"
check_contains "output is valid hookSpecificOutput JSON" "$OUT_ONE" '"hookEventName":"SessionStart"'

MULTI_FAILED='Installed plugins:

  ❯ ask-user@dgs-plugins
    Version: unknown
    Scope: user
    Status: ✖ failed to load — Marketplace dgs-plugins not found

  ❯ wiki@dgs-plugins
    Version: unknown
    Scope: user
    Status: ✖ failed to load — Marketplace dgs-plugins not found

  ❯ es6kr@es6kr-skills
    Version: 0.1.1
    Scope: user
    Status: ✔ enabled'

OUT_MULTI="$(run "$MULTI_FAILED")"
check_contains "multiple failures counted correctly" "$OUT_MULTI" "2 plugin(s) failed to load"
check_contains "multiple failures list first plugin" "$OUT_MULTI" "ask-user@dgs-plugins"
check_contains "multiple failures list second plugin" "$OUT_MULTI" "wiki@dgs-plugins"

# claude binary unresolvable — hook must fail open (no output, exit 0), never
# block session start just because the advisory check itself couldn't run.
# Resolve node's absolute path first so overriding PATH below only removes
# `claude` from resolution, not `node` itself.
NODE_BIN="$(command -v node)"
UNRESOLVABLE_OUT="$(PATH="/nonexistent" "$NODE_BIN" "$HOOK" SessionStart </dev/null; echo "exit=$?")"
check_contains "claude unresolvable fails open with exit 0" "$UNRESOLVABLE_OUT" "exit=0"

if [[ "$FAIL" -eq 0 ]]; then
  echo "All tests passed."
else
  echo "Some tests FAILED."
fi
exit "$FAIL"
