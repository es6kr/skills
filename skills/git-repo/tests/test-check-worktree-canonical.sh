#!/usr/bin/env bash
# Tests for check-worktree-canonical.sh — the worktree-reuse path-canonicality pre-check.
#
# `git` is stubbed via PATH so the test is deterministic/offline: the stub emits a canned
# `git worktree list --porcelain` payload from $STUB_WT_LIST. A real temp dir stands in for
# <repo> so its absolute path resolves; the canned worktree paths are built from it, so the
# canonical base ($REPO/.worktrees) matches (or not) purely by string.
#
# Run:  bash skills/git-repo/tests/test-check-worktree-canonical.sh
# Exit: 0 = all pass, 1 = any fail.

set -u
SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/scripts/check-worktree-canonical.sh"
[[ -f "$SCRIPT" ]] || { echo "script not found: $SCRIPT" >&2; exit 1; }

REPO="$(mktemp -d)"
STUBDIR="$(mktemp -d)"
cat > "$STUBDIR/git" <<'EOF'
#!/usr/bin/env bash
# minimal git stub: emits $STUB_WT_LIST for `worktree list --porcelain`, ignores the rest
printf '%s\n' "${STUB_WT_LIST:-}"
EOF
chmod +x "$STUBDIR/git"
trap 'rm -rf "$REPO" "$STUBDIR"' EXIT
FAIL=0

run() { # $1 = STUB_WT_LIST, $2 = target arg, [$3.. = extra flags]
  local list="$1" target="$2"; shift 2
  STUB_WT_LIST="$list" PATH="$STUBDIR:$PATH" bash "$SCRIPT" "$REPO" "$target" "$@" >/dev/null 2>&1
  echo $?
}
check() { # name want got
  if [[ "$3" == "$2" ]]; then echo "PASS  $1 (exit=$3)"; else echo "FAIL  $1 (exit=$3 want=$2)"; FAIL=1; fi
}

CANON="worktree $REPO/.worktrees/foo
HEAD 0000000
branch refs/heads/foo"

# 1. canonical parent (<repo>/.worktrees/) → CANONICAL
check "canonical (name)" 0 "$(run "$CANON" foo)"

# 2. canonical, addressed by full path → CANONICAL
check "canonical (path)" 0 "$(run "$CANON" "$REPO/.worktrees/foo")"

# 3. legacy .claude/worktrees/ → NON-CANONICAL
LEGACY="worktree $REPO/.claude/worktrees/bar
HEAD 0000000
branch refs/heads/bar"
check "legacy .claude/worktrees" 1 "$(run "$LEGACY" bar)"

# 4. sibling <repo>-wt/ → NON-CANONICAL
SIB="worktree ${REPO}-wt/baz
HEAD 0000000
branch refs/heads/baz"
check "sibling <repo>-wt" 1 "$(run "$SIB" baz)"

# 5. a .worktrees dir but NOT under this repo (e.g. a bare ~/.worktrees/) → NON-CANONICAL
BARE="worktree /tmp/elsewhere/.worktrees/qux
HEAD 0000000
branch refs/heads/qux"
check "foreign .worktrees" 1 "$(run "$BARE" qux)"

# 6. name not present in worktree list → NOT-REGISTERED
check "not registered" 2 "$(run "$CANON" nonexistent)"

# 7. --wt-base override: canonical under a custom base name
CUSTOM="worktree $REPO/wt/foo
HEAD 0000000
branch refs/heads/foo"
check "custom --wt-base match" 0 "$(run "$CUSTOM" foo --wt-base wt)"

# 8. --wt-base override: default .worktrees is non-canonical when base is 'wt'
check "custom --wt-base mismatch" 1 "$(run "$CANON" foo --wt-base wt)"

echo ""
if [[ "$FAIL" -eq 0 ]]; then echo "ALL PASS"; else echo "SOME FAILED"; fi
exit "$FAIL"
