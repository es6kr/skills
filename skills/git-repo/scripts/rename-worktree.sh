#!/usr/bin/env bash
# rename-worktree.sh — git worktree rename (directory + metadata + branch)
# Usage: rename-worktree.sh <repo> <old-name> <new-name> [--branch <branch>]
#
# <old-name>: directory name under .claude/worktrees/
# <new-name>: new directory name
# --branch:   branch to switch to (default: keep current branch)

set -euo pipefail

REPO="${1:?Usage: rename-worktree.sh <repo> <old-name> <new-name> [--branch <branch>]}"
OLD="${2:?missing old-name}"
NEW="${3:?missing new-name}"
BRANCH=""

shift 3
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) BRANCH="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Windows compatibility: git metadata files must contain Windows-style paths
# (C:/...) not Unix-style (/c/...). Bash filesystem ops keep Unix paths.
if command -v cygpath >/dev/null 2>&1; then
  REPO_WIN="$(cygpath -m "$REPO")"
else
  REPO_WIN="$REPO"
fi

WT_BASE="$REPO/.claude/worktrees"
WT_BASE_WIN="$REPO_WIN/.claude/worktrees"
OLD_PATH="$WT_BASE/$OLD"
NEW_PATH="$WT_BASE/$NEW"
NEW_PATH_WIN="$WT_BASE_WIN/$NEW"
GIT_WT_BASE="$REPO/.git/worktrees"
GIT_WT_BASE_WIN="$REPO_WIN/.git/worktrees"

if [[ ! -d "$OLD_PATH" ]]; then
  echo "ERROR: $OLD_PATH does not exist" >&2; exit 1
fi
if [[ -d "$NEW_PATH" ]]; then
  echo "ERROR: $NEW_PATH already exists" >&2; exit 1
fi

# 0. Resolve the actual metadata directory name from the worktree's .git file.
# Git may use a suffixed directory name (e.g., "<name>_1") when collisions exist,
# so we must not assume the metadata dir is named exactly $OLD.
ACTUAL_OLD_META="$OLD"
if [[ -f "$OLD_PATH/.git" ]]; then
  GITDIR_LINE=$(grep -E '^gitdir:' "$OLD_PATH/.git" || true)
  if [[ -n "$GITDIR_LINE" ]]; then
    META_PATH=$(echo "$GITDIR_LINE" | sed -E 's/^gitdir:[[:space:]]+//')
    ACTUAL_OLD_META=$(basename "$META_PATH")
  fi
fi
if [[ ! -d "$GIT_WT_BASE/$ACTUAL_OLD_META" ]]; then
  echo "ERROR: metadata directory not found at $GIT_WT_BASE/$ACTUAL_OLD_META" >&2
  echo "       (resolved from $OLD_PATH/.git; check 'git worktree list --porcelain')" >&2
  exit 1
fi

# 1. Rename worktree directory
mv "$OLD_PATH" "$NEW_PATH"

# 2. Rename .git/worktrees metadata (using the actual directory name)
mv "$GIT_WT_BASE/$ACTUAL_OLD_META" "$GIT_WT_BASE/$NEW"

# 3. Update .git file in worktree → point to new metadata (Windows-style path)
echo "gitdir: $GIT_WT_BASE_WIN/$NEW" > "$NEW_PATH/.git"

# 4. Update gitdir in metadata → point to new worktree (Windows-style path).
# Guard: the metadata dir must exist (Step 2 succeeded) before writing into it.
if [[ ! -d "$GIT_WT_BASE/$NEW" ]]; then
  echo "ERROR: metadata directory $GIT_WT_BASE/$NEW missing after rename — aborting to avoid broken state" >&2
  exit 1
fi
echo "$NEW_PATH_WIN/.git" > "$GIT_WT_BASE/$NEW/gitdir"

# 5. Verify
cd "$REPO"
git worktree repair 2>/dev/null || true

# 6. Switch branch if requested
if [[ -n "$BRANCH" ]]; then
  cd "$NEW_PATH"
  if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    git checkout "$BRANCH"
  elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH" 2>/dev/null; then
    git checkout -b "$BRANCH" "origin/$BRANCH"
  else
    git checkout -b "$BRANCH" HEAD
  fi
fi

# 7. Report
cd "$REPO"
echo "✓ Renamed: $OLD → $NEW"
# Use --porcelain + exact path match to avoid false negatives and to keep
# set -euo pipefail from aborting on grep no-match.
if git worktree list --porcelain | grep -qE "^worktree[[:space:]]+${NEW_PATH}$"; then
  git worktree list | grep -F "$NEW_PATH" || true
else
  echo "(worktree not listed yet — 'git worktree repair' may be needed)"
fi
if [[ -n "$BRANCH" ]]; then
  echo "✓ Branch: $BRANCH"
fi
