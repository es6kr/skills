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

# 1. Rename worktree directory
mv "$OLD_PATH" "$NEW_PATH"

# 2. Rename .git/worktrees metadata
if [[ -d "$GIT_WT_BASE/$OLD" ]]; then
  mv "$GIT_WT_BASE/$OLD" "$GIT_WT_BASE/$NEW"
fi

# 3. Update .git file in worktree → point to new metadata (Windows-style path)
echo "gitdir: $GIT_WT_BASE_WIN/$NEW" > "$NEW_PATH/.git"

# 4. Update gitdir in metadata → point to new worktree (Windows-style path)
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
git worktree list | grep "$NEW"
if [[ -n "$BRANCH" ]]; then
  echo "✓ Branch: $BRANCH"
fi
