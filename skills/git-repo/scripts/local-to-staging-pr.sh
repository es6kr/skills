#!/usr/bin/env bash
# local-to-staging-pr.sh — cherry-pick a commit from the local branch to a
# staging branch (next-feat/next-fix) feature branch, and print manual commands to push and open a draft PR.
#
# Encodes the es6kr/skills "2-tier review model" flow (see the
# agents-local-branch-nopush.md workspace rule's staging-flow procedure):
# local branch accumulates work, staging-base feature branches carry it to
# next-feat/next-fix, which merge without a per-PR review — the real review
# gate is the later promotion PR.
#
# Usage:
#   local-to-staging-pr.sh <repo-dir> <commit-sha> [--branch <name>] [--base <next-feat|next-fix>] [--push [--body-file <path>]]
#
# <repo-dir>:   path to the repo working copy (e.g. ~/.agents)
# <commit-sha>: commit to cherry-pick (must exist on the local branch)
# --branch:     feature branch name (default: derived from the commit subject)
# --base:       override the auto-derived base (feat -> next-feat, fix/chore -> next-fix)
# --push:       after a clean cherry-pick, also `git push -u origin <branch>`. The
#               caller (a human explicitly opting in per-invocation, mirroring the
#               same confirmation a bare `git push` would need) decides when this
#               is appropriate — the script never pushes by default.
# --body-file:  only meaningful with --push. Path to an ALREADY-AUTHORED PR body
#               file — when given, also runs `gh pr create --draft` with it. PR
#               title/body content still goes through human authorship before
#               this flag is used; this only automates the ceremony around
#               content someone already wrote and reviewed.
#
# On cherry-pick conflict, the script stops and reports the conflicted files —
# conflict resolution is not automated (case-by-case judgment required, see
# session precedent: prefer the newer/more-refined side after manual diff).
#
# Without --push: does NOT push or create the PR (prints the manual commands
# instead — unchanged default behavior). Never force-pushes, with or without
# --push.

set -euo pipefail

REPO="${1:?Usage: local-to-staging-pr.sh <repo-dir> <commit-sha> [--branch <name>] [--base <next-feat|next-fix>] [--push [--body-file <path>]]}"
SHA="${2:?missing commit-sha}"
BRANCH_OVERRIDE=""
BASE_OVERRIDE=""
DO_PUSH=0
BODY_FILE=""

shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) BRANCH_OVERRIDE="$2"; shift 2 ;;
    --base) BASE_OVERRIDE="$2"; shift 2 ;;
    --push) DO_PUSH=1; shift ;;
    --body-file) BODY_FILE="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -n "$BODY_FILE" && "$DO_PUSH" -eq 0 ]]; then
  echo "--body-file requires --push" >&2
  exit 1
fi
if [[ -n "$BODY_FILE" && ! -f "$BODY_FILE" ]]; then
  echo "--body-file path does not exist: $BODY_FILE" >&2
  exit 1
fi

cd "$REPO"

SUBJECT=$(git log -1 --format='%s' "$SHA")
TAG=$(echo "$SUBJECT" | grep -oE '^[a-z]+' || echo "")

if [[ -n "$BASE_OVERRIDE" ]]; then
  BASE="$BASE_OVERRIDE"
elif [[ "$TAG" == "feat" ]]; then
  BASE="next-feat"
elif [[ "$TAG" == "fix" || "$TAG" == "chore" ]]; then
  BASE="next-fix"
else
  echo "Cannot auto-derive base from tag '$TAG' (subject: $SUBJECT). Pass --base explicitly." >&2
  exit 1
fi

if [[ -z "$BRANCH_OVERRIDE" ]]; then
  SLUG=$(echo "$SUBJECT" | sed -E 's/^[a-z]+(\([a-z0-9_-]+\))?:[[:space:]]*//' | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed -E 's/-+/-/g; s/^-|-$//g' | cut -c1-40)
  if [[ -z "$SLUG" ]]; then
    SLUG="pr-cherry-pick-${SHA:0:7}"
  fi
  BRANCH="${TAG}/${SLUG}"
else
  BRANCH="$BRANCH_OVERRIDE"
fi

echo "== commit: $SHA ($SUBJECT)"
echo "== tag: $TAG -> base: $BASE"
echo "== feature branch: $BRANCH"

git fetch origin "$BASE"

# Pre-flight scaffolding check: verify every skill directory the commit
# touches has a SKILL.md on the target base (staging branches can lag behind
# local — see session precedent where hook-kit/ existed on local but only
# had resources/ on next-fix, causing a pre-push lint failure after the
# cherry-pick already happened).
CHANGED_SKILLS=$(git show --name-only --format= "$SHA" | grep -oE '^skills/[^/]+' | sort -u || true)
MISSING=0
for skill_dir in $CHANGED_SKILLS; do
  if ! git cat-file -e "origin/${BASE}:${skill_dir}/SKILL.md" 2>/dev/null; then
    echo "WARNING: ${skill_dir}/SKILL.md does not exist on origin/${BASE} — this skill's scaffolding may be incomplete on this staging branch." >&2
    MISSING=1
  fi
done
if [[ "$MISSING" -eq 1 ]]; then
  echo "Aborting before worktree creation. Pick a different base with --base, or land the skill scaffolding on ${BASE} first." >&2
  exit 1
fi

WT_DIR=".claude/worktrees/$(echo "$BRANCH" | tr '/' '-')"

# Reuse-first hygiene (non-interactive subset of worktree.md's "Worktree
# decision tree" — Steps 1-3): before adding a new worktree, inventory
# existing ones under .claude/worktrees/ and reclaim any whose branch is
# already merged into origin/main. Merged branches have no unique commits,
# so removal is safe without user confirmation; left unpruned they
# accumulate across repeated script runs. This does NOT replace the
# interactive reuse-first gate for *unmerged* inactive candidates — that
# choice requires a human (AskUserQuestion), which a non-interactive script
# cannot make, so it stays the plain-base manual path's responsibility.
while IFS= read -r wt_path; do
  [[ -z "$wt_path" || "$wt_path" != "$REPO"/.claude/worktrees/* ]] && continue
  wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null || true)
  [[ -z "$wt_branch" ]] && continue
  if git merge-base --is-ancestor "$wt_branch" origin/main 2>/dev/null; then
    echo "Reclaiming already-merged worktree: $wt_path ($wt_branch)" >&2
    git worktree remove "$wt_path" --force 2>/dev/null || true
    git branch -D "$wt_branch" 2>/dev/null || true
  fi
done < <(git worktree list --porcelain | awk '/^worktree /{print $2}')

if [[ -d "$WT_DIR" ]]; then
  echo "Worktree already exists at $WT_DIR — remove it first or pass a different --branch." >&2
  exit 1
fi

CLEANUP_REQUIRED=0
cleanup_worktree() {
  if [[ -d "${WT_DIR:-}" ]] && [[ "${CLEANUP_REQUIRED:-0}" -eq 1 ]]; then
    echo "Cleaning up dangling worktree at $WT_DIR..." >&2
    git worktree remove "$WT_DIR" --force 2>/dev/null || true
    git branch -D "$BRANCH" 2>/dev/null || true
  fi
}
trap cleanup_worktree EXIT INT TERM

CLEANUP_REQUIRED=1
git worktree add "$WT_DIR" -b "$BRANCH" "origin/$BASE"

# LC_ALL=C forces English git output regardless of the local git locale
# config, so the empty-cherry-pick detection below doesn't need a localized
# string match.
CP_FAILED=0
CP_OUTPUT=$(LC_ALL=C git -C "$WT_DIR" cherry-pick "$SHA" 2>&1) || CP_FAILED=1
echo "$CP_OUTPUT"
if [[ "$CP_FAILED" -eq 1 ]]; then
  if echo "$CP_OUTPUT" | grep -qE 'previous cherry-pick is now empty'; then
    echo "" >&2
    echo "Commit $SHA is already applied on origin/$BASE (empty cherry-pick) — nothing to do." >&2
    git -C "$WT_DIR" cherry-pick --abort 2>/dev/null || true
    CLEANUP_REQUIRED=1 # Ensure removal
    cleanup_worktree
    CLEANUP_REQUIRED=0
    exit 0
  fi
  echo "" >&2
  echo "Cherry-pick conflict. Resolve manually in $WT_DIR, then:" >&2
  echo "  git -C $WT_DIR add <resolved-files>" >&2
  echo "  git -C $WT_DIR cherry-pick --continue" >&2
  echo "  git -C $WT_DIR push -u origin $BRANCH   # push manually after resolving" >&2
  # Keep worktree intact for manual resolution
  CLEANUP_REQUIRED=0
  exit 1
fi

CLEANUP_REQUIRED=0
echo "== cherry-pick clean"

# Korean-text check (surfaces any Korean text before you push).
if ! python3 "$REPO/scripts/check-hangul.py" "$WT_DIR/skills" >/dev/null 2>&1; then
  echo "WARNING: Korean text detected outside data/ — push will likely be rejected by the pre-commit/pre-push hooks." >&2
fi

chmod +x "$WT_DIR/.githooks/pre-commit" 2>/dev/null || true

if [[ "$DO_PUSH" -eq 0 ]]; then
  echo "== ready to push: git -C $WT_DIR push -u origin $BRANCH"
  echo "== then: gh pr create -R es6kr/skills --base $BASE --head $BRANCH --draft --title \"$SUBJECT\" --body-file <sanitized-body.md>"
  echo "== (push/PR creation left manual — this script stops after the clean cherry-pick + pre-flight checks. Pass --push to also push, and --push --body-file <path> to also open the draft PR from an already-authored body.)"
  exit 0
fi

echo "== pushing (--push given)"
git -C "$WT_DIR" push -u origin "$BRANCH"

if [[ -z "$BODY_FILE" ]]; then
  echo "== pushed. PR creation left manual (no --body-file given):"
  echo "  gh pr create -R es6kr/skills --base $BASE --head $BRANCH --draft --title \"$SUBJECT\" --body-file <sanitized-body.md>"
  exit 0
fi

echo "== opening draft PR (--body-file given)"
PR_URL=$(gh pr create -R es6kr/skills --base "$BASE" --head "$BRANCH" --draft --title "$SUBJECT" --body-file "$BODY_FILE")
echo "== draft PR: $PR_URL"
