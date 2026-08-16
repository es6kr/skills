#!/usr/bin/env bash
# rename-worktree.sh — git worktree rename (directory + metadata + branch)
# Usage: rename-worktree.sh <repo> <old-name> <new-name> [--branch <branch>] [--base <ref>] [--wt-base <dir>]
#
# <old-name>:  directory name under the worktree base
# <new-name>:  new directory name
# --branch:    branch to switch to (default: keep current branch)
# --base:      base ref for a NEWLY created branch (e.g. origin/main). Ignored when
#              --branch names a branch that already exists locally or on origin.
#              Without it a new branch starts at the worktree's current HEAD — which,
#              in this script's primary use case (reclaiming an inactive worktree),
#              is the stale tip of the work that worktree used to hold.
# --wt-base:   worktree base dir relative to <repo> (default: .claude/worktrees).
#              Use e.g. --wt-base .worktrees for repos that keep worktrees at <repo>/.worktrees/

set -euo pipefail

REPO="${1:?Usage: rename-worktree.sh <repo> <old-name> <new-name> [--branch <branch>]}"
OLD="${2:?missing old-name}"
NEW="${3:?missing new-name}"
BRANCH=""
BASE=""
WT_BASE_REL=".claude/worktrees"

shift 3
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) BRANCH="$2"; shift 2 ;;
    --base) BASE="$2"; shift 2 ;;
    --wt-base) WT_BASE_REL="${2#/}"; WT_BASE_REL="${WT_BASE_REL%/}"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Windows compatibility: git metadata files must contain Windows-style paths
# (C:/...) not MSYS (/c/...) or WSL (/mnt/c/...). Bash filesystem ops keep Unix paths.
if command -v cygpath >/dev/null 2>&1; then
  REPO_WIN="$(cygpath -m "$REPO")"
elif command -v wslpath >/dev/null 2>&1 && [[ "$REPO" == /mnt/?/* ]]; then
  REPO_WIN="$(wslpath -w "$REPO" | tr '\\' '/')"
else
  REPO_WIN="$REPO"
fi

WT_BASE="$REPO/$WT_BASE_REL"
WT_BASE_WIN="$REPO_WIN/$WT_BASE_REL"
OLD_PATH="$WT_BASE/$OLD"
NEW_PATH="$WT_BASE/$NEW"
NEW_PATH_WIN="$WT_BASE_WIN/$NEW"

# Default GIT_WT_BASE assumes a non-bare layout where <repo>/.git is a directory.
# In a bare-with-worktree layout (e.g., ~/.agents whose .git is a gitdir-file
# pointing into a separate bare repo at ~/ghq/.../<repo>.git), this default is
# wrong. Step 0 below overrides it from the actual worktree .git pointer.
GIT_WT_BASE="$REPO/.git/worktrees"
GIT_WT_BASE_WIN="$REPO_WIN/.git/worktrees"

if [[ ! -d "$OLD_PATH" ]]; then
  echo "ERROR: $OLD_PATH does not exist" >&2; exit 1
fi
if [[ -d "$NEW_PATH" ]]; then
  echo "ERROR: $NEW_PATH already exists" >&2; exit 1
fi

# 0. Resolve the actual metadata directory + base from the worktree's .git file.
# Two concerns handled here:
#   (a) Git may use a suffixed directory name (e.g., "<name>_1") when collisions
#       exist, so we must not assume the metadata dir is named exactly $OLD.
#   (b) Bare-with-worktree layouts (e.g., ~/.agents whose .git is a gitdir-file
#       pointing into a separate bare repo) make the default GIT_WT_BASE wrong.
#       Override it with the actual parent of the metadata dir.
ACTUAL_OLD_META="$OLD"
if [[ -f "$OLD_PATH/.git" ]]; then
  GITDIR_LINE=$(grep -E '^gitdir:' "$OLD_PATH/.git" || true)
  if [[ -n "$GITDIR_LINE" ]]; then
    META_PATH=$(echo "$GITDIR_LINE" | sed -E 's/^gitdir:[[:space:]]+//')
    # Note: standard git writes an absolute `gitdir:` path here. Some setups
    # (worktree.useRelative = true, manual edits) may write a relative path —
    # if you hit a "metadata directory not found" error below with an unusual
    # META_PATH, run `git worktree repair` first to renormalize the .git file.
    ACTUAL_OLD_META=$(basename "$META_PATH")
    # Override GIT_WT_BASE with the actual parent — supports both layouts.
    GIT_WT_BASE=$(dirname "$META_PATH")
    if command -v cygpath >/dev/null 2>&1; then
      GIT_WT_BASE_WIN="$(cygpath -m "$GIT_WT_BASE")"
    else
      GIT_WT_BASE_WIN="$GIT_WT_BASE"
    fi
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
  elif [[ -n "$BASE" ]]; then
    git rev-parse --verify --quiet "$BASE" >/dev/null \
      || { echo "ERROR: --base '$BASE' does not resolve (fetch it first?)" >&2; exit 1; }
    git checkout -b "$BRANCH" "$BASE"
  else
    # No base given: start at the worktree's current HEAD. When this worktree is
    # being reclaimed from finished work, that HEAD is the stale tip of the old
    # branch, so the new branch silently inherits commits the caller did not want.
    # Cannot pick a default safely — the repo's integration branch is not always
    # main (staging-branch models exist) — so report what is being used instead.
    _head="$(git rev-parse --short HEAD)"
    _subject="$(git log -1 --format=%s)"
    echo "WARNING: new branch '$BRANCH' starts at HEAD ($_head: $_subject)." >&2
    if _up="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"; then
      _behind="$(git rev-list --count "HEAD..$_up" 2>/dev/null || echo '?')"
      echo "         HEAD is $_behind commit(s) behind $_up." >&2
    fi
    echo "         Pass --base <ref> (e.g. --base origin/main) to start elsewhere." >&2
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
