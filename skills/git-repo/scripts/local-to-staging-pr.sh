#!/usr/bin/env bash
# local-to-staging-pr.sh — cherry-pick a commit from the local branch to a
# staging branch (next-feat/next-fix) feature branch, push, and open a draft PR.
#
# Encodes the es6kr/skills "2-tier review model" flow (see the
# agents-local-branch-nopush.md workspace rule's staging-flow procedure):
# local branch accumulates work, staging-base feature branches carry it to
# next-feat/next-fix, which merge without a per-PR review — the real review
# gate is the later promotion PR.
#
# Usage:
#   local-to-staging-pr.sh <repo-dir> <commit-sha> [--branch <name>] [--base <next-feat|next-fix>]
#
# <repo-dir>:   path to the repo working copy (e.g. ~/.agents)
# <commit-sha>: commit to cherry-pick (must exist on the local branch)
# --branch:     feature branch name (default: derived from the commit subject)
# --base:       override the auto-derived base (feat -> next-feat, fix/chore -> next-fix)
#
# On cherry-pick conflict, the script stops and reports the conflicted files —
# conflict resolution is not automated (case-by-case judgment required, see
# session precedent: prefer the newer/more-refined side after manual diff).
#
# Does NOT push or create the PR without a clean cherry-pick. Does NOT force-push.

set -euo pipefail

REPO="${1:?Usage: local-to-staging-pr.sh <repo-dir> <commit-sha> [--branch <name>] [--base <next-feat|next-fix>]}"
SHA="${2:?missing commit-sha}"
BRANCH_OVERRIDE=""
BASE_OVERRIDE=""

shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) BRANCH_OVERRIDE="$2"; shift 2 ;;
    --base) BASE_OVERRIDE="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

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
  SLUG=$(echo "$SUBJECT" | sed -E 's/^[a-z]+(\([a-z0-9_-]+\))?:\s*//' | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed -E 's/-+/-/g; s/^-|-$//g' | cut -c1-40)
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
if [[ -d "$WT_DIR" ]]; then
  echo "Worktree already exists at $WT_DIR — remove it first or pass a different --branch." >&2
  exit 1
fi

git worktree add "$WT_DIR" -b "$BRANCH" "origin/$BASE"

# LC_ALL=C forces English git output regardless of the local git locale
# config, so the empty-cherry-pick detection below doesn't need a localized
# string match.
CP_OUTPUT=$(LC_ALL=C git -C "$WT_DIR" cherry-pick "$SHA" 2>&1) || CP_FAILED=1
echo "$CP_OUTPUT"
if [[ "${CP_FAILED:-0}" -eq 1 ]]; then
  if echo "$CP_OUTPUT" | grep -qE 'previous cherry-pick is now empty'; then
    echo "" >&2
    echo "Commit $SHA is already applied on origin/$BASE (empty cherry-pick) — nothing to do." >&2
    git -C "$WT_DIR" cherry-pick --abort 2>/dev/null || true
    git -C "$REPO" worktree remove "$WT_DIR" --force
    git -C "$REPO" branch -D "$BRANCH"
    exit 0
  fi
  echo "" >&2
  echo "Cherry-pick conflict. Resolve manually in $WT_DIR, then:" >&2
  echo "  git -C $WT_DIR add <resolved-files>" >&2
  echo "  git -C $WT_DIR cherry-pick --continue" >&2
  echo "  git -C $WT_DIR push -u origin $BRANCH   # push manually after resolving" >&2
  exit 1
fi

echo "== cherry-pick clean"

# Korean-text check mirrors the repo's pre-commit hook (defense in depth —
# the hook already ran during cherry-pick's internal commit, this just
# surfaces the result before push).
if grep -rlP '[\x{AC00}-\x{D7A3}]' "$WT_DIR" --include='*.md' --include='*.sh' 2>/dev/null | grep -v '/data/'; then
  echo "WARNING: Korean text detected outside data/ — push will likely be rejected by the pre-commit hook." >&2
fi

chmod +x "$WT_DIR/.githooks/pre-commit" 2>/dev/null || true

echo "== ready to push: git -C $WT_DIR push -u origin $BRANCH"
echo "== then: gh pr create -R es6kr/skills --base $BASE --head $BRANCH --draft --title \"$SUBJECT\" --body-file <sanitized-body.md>"
echo "== (push/PR creation left manual — this script stops after the clean cherry-pick + pre-flight checks)"
