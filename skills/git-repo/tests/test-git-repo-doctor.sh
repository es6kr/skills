#!/usr/bin/env bash
# Tests for git-repo-doctor.sh — Comprehensive Git repository and hook diagnostics.
#
# Tests both Tier 1 (Base checks) and Tier 2 (Conditional checks) against fixture repositories.
#
# Run:  bash skills/git-repo/tests/test-git-repo-doctor.sh
# Exit: 0 = all pass, 1 = any fail.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/../scripts/git-repo-doctor.sh"
[[ -f "$SCRIPT" ]] || { echo "script not found: $SCRIPT" >&2; exit 1; }

FAIL=0

check() {
  local name="$1"
  local want_exit="$2"
  local got_exit="$3"
  local out="${4:-}"
  if [[ "$got_exit" -eq "$want_exit" ]]; then
    echo "PASS  $name (exit=$got_exit)"
  else
    echo "FAIL  $name (exit=$got_exit want=$want_exit)"
    [[ -n "$out" ]] && echo "OUTPUT: $out"
    FAIL=1
  fi
}

REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
FIXTURE_BASE="$REPO_ROOT/.tmp/doctor_test_$$"
mkdir -p "$FIXTURE_BASE"
trap 'rm -rf "$FIXTURE_BASE"' EXIT

git_in() {
  local r="$1"; shift
  (cd "$r" && env -u GIT_DIR -u GIT_WORK_TREE git "$@")
}

make_temp_repo() {
  local repo="$FIXTURE_BASE/repo_${RANDOM}_$RANDOM"
  mkdir -p "$repo"
  git_in "$repo" init --quiet
  printf '%s' "$repo"
}

# -----------------------------------------------------------------------------
# Test 1: Base - Unwired .githooks directory (core.hooksPath not set)
# -----------------------------------------------------------------------------
REPO_1="$(make_temp_repo)"
mkdir -p "$REPO_1/.githooks"
cat > "$REPO_1/.githooks/pre-commit" << 'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$REPO_1/.githooks/pre-commit"
# core.hooksPath not configured, so .githooks/ is ignored by default
out_1=$(bash "$SCRIPT" "$REPO_1" 2>&1)
exit_1=$?
check "Base: unwired .githooks directory detected" 1 "$exit_1"
rm -rf "$REPO_1"

# -----------------------------------------------------------------------------
# Test 2: Base - Missing pre-push zero-SHA deletion early exit
# -----------------------------------------------------------------------------
REPO_2="$(make_temp_repo)"
mkdir -p "$REPO_2/.githooks"
git -C "$REPO_2" config core.hooksPath .githooks
cat > "$REPO_2/.githooks/pre-push" << 'EOF'
#!/bin/sh
# Has local guard but NO zero-SHA early exit!
while read line; do
  set -- $line
  if [ "$1" = "refs/heads/local" ]; then exit 1; fi
done
pytest tests
EOF
chmod +x "$REPO_2/.githooks/pre-push"
out_2=$(bash "$SCRIPT" "$REPO_2" 2>&1)
exit_2=$?
check "Base: pre-push missing zero-SHA early exit" 1 "$exit_2"
rm -rf "$REPO_2"

# -----------------------------------------------------------------------------
# Test 3: Base - Missing pre-push 'local' branch guard
# -----------------------------------------------------------------------------
REPO_3="$(make_temp_repo)"
mkdir -p "$REPO_3/.githooks"
git -C "$REPO_3" config core.hooksPath .githooks
cat > "$REPO_3/.githooks/pre-push" << 'EOF'
#!/bin/sh
# Has zero-SHA early exit but NO local branch guard
while read lref lsha rref rsha; do
  [ "$lsha" = "0000000000000000000000000000000000000000" ] && exit 0
done
EOF
chmod +x "$REPO_3/.githooks/pre-push"
out_3=$(bash "$SCRIPT" "$REPO_3" 2>&1)
exit_3=$?
check "Base: pre-push missing local branch guard" 1 "$exit_3"
rm -rf "$REPO_3"

# -----------------------------------------------------------------------------
# Test 4: Conditional - Markdown present without markdown lint hook
# -----------------------------------------------------------------------------
REPO_4="$(make_temp_repo)"
mkdir -p "$REPO_4/.githooks"
git_in "$REPO_4" config core.hooksPath .githooks
echo "# Title" > "$REPO_4/README.md"
git_in "$REPO_4" add README.md
git_in "$REPO_4" -c user.name="Test" -c user.email="test@test.com" commit -m "docs: add readme" --quiet
cat > "$REPO_4/.githooks/pre-commit" << 'EOF'
#!/bin/sh
# Only IP check, no markdown lint / text validation
grep -E '192\.168' .
EOF
cat > "$REPO_4/.githooks/pre-push" << 'EOF'
#!/bin/sh
while read lref lsha rref rsha; do
  [ "$lsha" = "0000000000000000000000000000000000000000" ] && exit 0
  if [ "$lref" = "refs/heads/local" ]; then exit 1; fi
done
EOF
chmod +x "$REPO_4/.githooks/pre-commit" "$REPO_4/.githooks/pre-push"
out_4=$(bash "$SCRIPT" "$REPO_4" 2>&1)
exit_4=$?
check "Conditional: markdown present without md lint hook" 1 "$exit_4"
rm -rf "$REPO_4"

# -----------------------------------------------------------------------------
# Test 5: Conditional - Skills present without skill frontmatter lint hook
# -----------------------------------------------------------------------------
REPO_5="$(make_temp_repo)"
mkdir -p "$REPO_5/.githooks" "$REPO_5/skills/test-skill"
git_in "$REPO_5" config core.hooksPath .githooks
cat > "$REPO_5/skills/test-skill/SKILL.md" << 'EOF'
---
name: test-skill
description: Test skill description
---
# Test Skill
EOF
git_in "$REPO_5" add skills/test-skill/SKILL.md
git_in "$REPO_5" -c user.name="Test" -c user.email="test@test.com" commit -m "feat: add test skill" --quiet
cat > "$REPO_5/.githooks/pre-commit" << 'EOF'
#!/bin/sh
# Generic md check
check-hangul.py
EOF
cat > "$REPO_5/.githooks/pre-push" << 'EOF'
#!/bin/sh
while read lref lsha rref rsha; do
  [ "$lsha" = "0000000000000000000000000000000000000000" ] && exit 0
  if [ "$lref" = "refs/heads/local" ]; then exit 1; fi
done
EOF
chmod +x "$REPO_5/.githooks/pre-commit" "$REPO_5/.githooks/pre-push"
out_5=$(bash "$SCRIPT" "$REPO_5" 2>&1)
exit_5=$?
check "Conditional: skills present without skill lint hook" 1 "$exit_5" "$out_5"
rm -rf "$REPO_5"

# -----------------------------------------------------------------------------
# Test 6: Fully Compliant Skills Repository (All Base & Conditional checks pass)
# -----------------------------------------------------------------------------
REPO_6="$(make_temp_repo)"
mkdir -p "$REPO_6/.githooks" "$REPO_6/skills/sample-skill"
git_in "$REPO_6" config core.hooksPath .githooks
cat > "$REPO_6/skills/sample-skill/SKILL.md" << 'EOF'
---
name: sample-skill
description: Sample skill
---
# Sample
EOF
git_in "$REPO_6" add skills/sample-skill/SKILL.md
git_in "$REPO_6" -c user.name="Test" -c user.email="test@test.com" commit -m "feat: add sample skill" --quiet

cat > "$REPO_6/.githooks/pre-commit" << 'EOF'
#!/bin/sh
# Check markdown / hangul
check-hangul.py
# Check IP / secrets
grep -E '192\.168\.' .
EOF

cat > "$REPO_6/.githooks/pre-push" << 'EOF'
#!/bin/sh
while read lref lsha rref rsha; do
  # Zero SHA early exit
  if [ "$lsha" = "0000000000000000000000000000000000000000" ] || [ "$lsha" = "(delete)" ]; then
    exit 0
  fi
  # Local branch push guard
  if [ "$lref" = "refs/heads/local" ]; then
    exit 1
  fi
  # Push commit count limit guard
  MAX_COMMITS="${PUSH_MAX_COMMITS:-5}"
  COUNT=$(git rev-list --count origin/main.."$lsha" 2>/dev/null || echo 0)
  if [ "$COUNT" -gt "$MAX_COMMITS" ] && [ "${PUSH_COMMIT_LIMIT_OVERRIDE:-0}" != "1" ]; then
    exit 1
  fi

  # Conflict marker guard
  CONFLICT_COMMITS=$(git rev-list origin/main.."$lsha" 2>/dev/null | while read -r sha; do
    git log -1 --format='%B' "$sha" | grep -qE '^#?[[:space:]]*Conflicts:' && echo "$sha"
  done)
  if [ -n "$CONFLICT_COMMITS" ] && [ "${PUSH_CONFLICT_MSG_OVERRIDE:-0}" != "1" ]; then
    exit 1
  fi

done
# Skill frontmatter & language lint
bash scripts/lint-frontmatter.sh
EOF

chmod +x "$REPO_6/.githooks/pre-commit" "$REPO_6/.githooks/pre-push"
out_6=$(bash "$SCRIPT" "$REPO_6" 2>&1)
exit_6=$?
check "Fully compliant repository passes all checks" 0 "$exit_6"
rm -rf "$REPO_6"

# -----------------------------------------------------------------------------
# Test 7: Base - Missing pre-push commit count limit guard (BASE-6)
# -----------------------------------------------------------------------------
REPO_7="$(make_temp_repo)"
mkdir -p "$REPO_7/.githooks"
git_in "$REPO_7" config core.hooksPath .githooks
cat > "$REPO_7/.githooks/pre-push" << 'EOF'
#!/bin/sh
while read lref lsha rref rsha; do
  [ "$lsha" = "0000000000000000000000000000000000000000" ] && exit 0
  if [ "$lref" = "refs/heads/local" ]; then exit 1; fi
done
EOF
chmod +x "$REPO_7/.githooks/pre-push"
out_7=$(bash "$SCRIPT" "$REPO_7" 2>&1)
exit_7=$?
check "Base: pre-push missing commit count limit guard (BASE-6)" 1 "$exit_7"
rm -rf "$REPO_7"

# -----------------------------------------------------------------------------
# Test 8: Base - Missing pre-push conflict marker guard (BASE-7)
# -----------------------------------------------------------------------------
REPO_8="$(make_temp_repo)"
mkdir -p "$REPO_8/.githooks"
git_in "$REPO_8" config core.hooksPath .githooks
cat > "$REPO_8/.githooks/pre-push" << 'EOF'
#!/bin/sh
while read lref lsha rref rsha; do
  [ "$lsha" = "0000000000000000000000000000000000000000" ] && exit 0
  if [ "$lref" = "refs/heads/local" ]; then exit 1; fi
  MAX_COMMITS="${PUSH_MAX_COMMITS:-5}"
  COUNT=$(git rev-list --count origin/main.."$lsha" 2>/dev/null || echo 0)
  if [ "$COUNT" -gt "$MAX_COMMITS" ] && [ "${PUSH_COMMIT_LIMIT_OVERRIDE:-0}" != "1" ]; then exit 1; fi
done
EOF
chmod +x "$REPO_8/.githooks/pre-push"
out_8=$(bash "$SCRIPT" "$REPO_8" 2>&1)
exit_8=$?
check "Base: pre-push missing conflict marker guard (BASE-7)" 1 "$exit_8"
rm -rf "$REPO_8"

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
fi

exit "$FAIL"
