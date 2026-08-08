#!/usr/bin/env bash
# stage-isolated-content.sh <repo-dir> <path> <content-file>
#
# Stages <content-file> as the index entry for <path>, without touching the
# working tree copy of <path> at all. Use this when a tracked file's working
# tree mixes your own edit with unrelated uncommitted content (e.g. a shared
# skills monorepo where another session/device has concurrent work-in-progress
# in the same file), and you need to commit only your own change.
#
# See isolate-hunk.md for the full workflow (building <content-file> from
# HEAD + your intended insertion before calling this script).
#
# Usage:
#   stage-isolated-content.sh <repo-dir> <path> <content-file>
#
# <repo-dir>:     path to the repo working copy
# <path>:         path relative to repo root (must match an existing tracked file)
# <content-file>: file containing the exact content you want staged for <path>
#
# Exits non-zero and leaves the index untouched if verification fails.

set -euo pipefail

REPO="${1:?Usage: stage-isolated-content.sh <repo-dir> <path> <content-file>}"
TARGET_PATH="${2:?missing path}"
CONTENT_FILE="${3:?missing content-file}"

cd "$REPO"

if [[ ! -f "$CONTENT_FILE" ]]; then
  echo "content-file not found: $CONTENT_FILE" >&2
  exit 1
fi

# Preserve the target's existing tracked mode (100644 vs 100755) — hardcoding
# 100644 here would silently drop the executable bit on any script being
# isolated (caught in session precedent: an isolated .sh file lost +x, and a
# follow-up `update-index --chmod=+x` on the cacheinfo-only entry made git
# re-read the blob from the working tree, reintroducing the very unrelated
# content this technique exists to keep out — fix the mode in the same
# --cacheinfo call instead of a separate chmod step).
MODE=$(git ls-tree HEAD -- "$TARGET_PATH" | awk '{print $1}')
if [[ -z "$MODE" ]]; then
  echo "Could not determine tracked mode for $TARGET_PATH (not found in HEAD) — falling back to 100644." >&2
  MODE=100644
fi

BLOB=$(git hash-object -w "$CONTENT_FILE")
git update-index --cacheinfo "$MODE","$BLOB","$TARGET_PATH"

echo "== staged $TARGET_PATH as blob $BLOB (mode $MODE)"

if git show ":$TARGET_PATH" | diff -q - "$CONTENT_FILE" >/dev/null; then
  echo "== verified: staged content matches $CONTENT_FILE exactly"
else
  echo "VERIFICATION FAILED: staged content does not match $CONTENT_FILE" >&2
  exit 1
fi

echo "== working tree copy of $TARGET_PATH is untouched — ready to commit"
