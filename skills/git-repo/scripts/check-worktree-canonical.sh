#!/usr/bin/env bash
# check-worktree-canonical.sh — pre-check that a worktree lives under the canonical
# <repo>/.worktrees/ base BEFORE it is reused (rename-worktree.sh / manual branch switch).
#
# Automates the currently-manual path-canonicality gate:
#   - worktree.md §4A row 3 + "Path-canonicality applies regardless" note
#   - worktree.md Don't/Do #9 + "before reusing any inactive candidate" self-check
#   - move-worktree.md Scenario C step 1
# Reusing a non-canonically-located worktree via rename-worktree.sh alone perpetuates
# its wrong location indefinitely — this detector catches that before reuse.
#
# Detect-only by design: it REPORTS and exits non-zero when non-canonical; it does NOT
# relocate. The relocation stays a deliberate move-worktree.md Scenario B step so no
# worktree is mutated without an explicit decision.
#
# Usage:
#   check-worktree-canonical.sh <repo> <worktree-name-or-path> [--wt-base <dir>]
#     <repo>:                    path to the main repo (the worktree owner)
#     <worktree-name-or-path>:   a registered worktree's directory name (final path
#                                component) OR an absolute/relative path to it
#     --wt-base <dir>:           canonical base dir relative to <repo> (default: .worktrees)
#
# Exit codes:
#   0  CANONICAL      — parent dir == <repo>/<wt-base>  → safe to reuse in place
#   1  NON-CANONICAL  — parent dir != canonical base    → relocate (Scenario B) first
#   2  NOT-REGISTERED — not found in `git worktree list` → orphan dir (Scenario A) / not a repo
#   3  usage / argument error
#   4  AMBIGUOUS      — bare name matches 2+ registered worktrees → re-run with an explicit path

set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 3; }

[[ $# -ge 2 ]] || die "usage: check-worktree-canonical.sh <repo> <worktree-name-or-path> [--wt-base <dir>]"

REPO="$1"; TARGET="$2"; shift 2
WT_BASE_REL=".worktrees"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt-base) [[ $# -ge 2 ]] || die "--wt-base needs a value"
               WT_BASE_REL="${2#/}"; WT_BASE_REL="${WT_BASE_REL%/}"; shift 2 ;;
    *) die "unknown option: $1" ;;
  esac
done

# Pure-string path normalization: collapse repeated slashes + strip trailing slash.
# No filesystem access and no symlink resolution — git emits absolute worktree paths,
# so string comparison of normalized paths is sufficient for this heuristic pre-check
# (the real non-canonical cases — .claude/worktrees/, <repo>-wt/, a bare ~/.worktrees/ —
# all differ at the string level). Kept filesystem-free so it is testable with canned
# `git worktree list` output and bash-3.2 safe (macOS default shell).
normpath() {
  local p
  p="$(printf '%s' "$1" | sed -E 's#/+#/#g; s#(.)/$#\1#')"
  [[ -z "$p" ]] && p="/"
  printf '%s' "$p"
}

# Resolve <repo> to an absolute path when it exists (nicer relocation command in the
# report); fall back to the given value otherwise (e.g. offline/test with a canned repo).
if [[ -d "$REPO" ]]; then
  REPO_ABS="$(cd "$REPO" 2>/dev/null && pwd)"
  [[ -n "$REPO_ABS" ]] || REPO_ABS="$REPO"
else
  REPO_ABS="$REPO"
fi

CANON_BASE="$(normpath "$REPO_ABS/$WT_BASE_REL")"

# Classify the target: a path (matched by normalized full path) or a bare name
# (matched by the worktree's final path component).
is_pathlike=0
case "$TARGET" in
  /*|./*|../*|*/*) is_pathlike=1 ;;
esac
[[ -e "$TARGET" ]] && is_pathlike=1

TARGET_NORM=""
if [[ $is_pathlike -eq 1 ]]; then
  case "$TARGET" in
    /*) TARGET_NORM="$(normpath "$TARGET")" ;;
    *)  TARGET_NORM="$(normpath "$PWD/$TARGET")" ;;
  esac
fi

WT_LIST="$(git -C "$REPO_ABS" worktree list --porcelain 2>/dev/null || true)"

# The main repository worktree is always the first `worktree` entry in the porcelain
# output; it is not a linked/reusable worktree, so exclude it from matching entirely
# (both by path and by basename) — otherwise a bare-name target that happens to equal
# the repo's own directory name would incorrectly "match" it.
MAIN_NORM="$(normpath "$REPO_ABS")"

MATCH=""
MATCH_COUNT=0
ALL_MATCHES=""
while IFS= read -r line; do
  case "$line" in
    "worktree "*)
      wt="${line#worktree }"
      wt_norm="$(normpath "$wt")"
      [[ "$wt_norm" == "$MAIN_NORM" ]] && continue
      if [[ $is_pathlike -eq 1 ]]; then
        [[ "$wt_norm" == "$TARGET_NORM" ]] && { MATCH="$wt_norm"; MATCH_COUNT=1; break; }
      else
        if [[ "$(basename "$wt_norm")" == "$TARGET" ]]; then
          MATCH_COUNT=$((MATCH_COUNT + 1))
          MATCH="$wt_norm"
          ALL_MATCHES="${ALL_MATCHES}${ALL_MATCHES:+$'\n'}  $wt_norm"
        fi
      fi
      ;;
  esac
done <<< "$WT_LIST"

if [[ $is_pathlike -eq 0 && $MATCH_COUNT -gt 1 ]]; then
  echo "AMBIGUOUS: '$TARGET' matches $MATCH_COUNT registered worktrees by basename:" >&2
  echo "$ALL_MATCHES" >&2
  echo "  → re-run with an explicit path (not a bare name) to disambiguate." >&2
  exit 4
fi

if [[ -z "$MATCH" ]]; then
  echo "NOT-REGISTERED: '$TARGET' not found in \`git worktree list\` for $REPO_ABS" >&2
  echo "  → orphan directory (move-worktree.md Scenario A), the main repository worktree (not a linked worktree), or <repo> is not a git repo." >&2
  exit 2
fi

WT_PARENT="$(normpath "$(dirname "$MATCH")")"

if [[ "$WT_PARENT" == "$CANON_BASE" ]]; then
  echo "CANONICAL: $MATCH"
  echo "  parent = $WT_PARENT  (== <repo>/$WT_BASE_REL)"
  echo "  → safe to reuse in place (rename-worktree.sh / manual branch switch)."
  exit 0
fi

echo "NON-CANONICAL: $MATCH" >&2
echo "  parent    = $WT_PARENT" >&2
echo "  canonical = $CANON_BASE" >&2
echo "  → relocate to the canonical base BEFORE reuse (move-worktree.md Scenario B):" >&2
echo "      git -C $REPO_ABS worktree move '$MATCH' '$CANON_BASE/$(basename "$MATCH")'" >&2
echo "    NOTE: \`git worktree move\` is known to be unreliable on Windows — on Windows," >&2
echo "    delegate to the rename-worktree.sh script/procedure instead (see move-worktree.md)." >&2
echo "    then proceed with rename-worktree.sh / the branch switch." >&2
exit 1
