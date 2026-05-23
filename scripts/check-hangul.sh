#!/usr/bin/env bash
# check-hangul.sh — Verify no Korean text remains in skill directories before publishing.
# Usage: bash check-hangul.sh [skills-parent-dir]
#        bash check-hangul.sh <skill-dir1> [skill-dir2] ...
#
# Two invocation modes:
#   (1) Parent mode: pass a single directory containing skill subdirs (e.g., `skills`).
#       Iterates each immediate subdir as a skill. This is the recommended CI mode
#       (avoids shell glob expansion surprises when the parent is empty).
#   (2) Explicit mode: pass one or more individual skill directories.
#
# Scans all .md and .sh files for Korean characters (Hangul).
# Exit codes:
#   0 = all clean
#   1 = Korean text found

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

if [[ $# -eq 0 ]]; then
  set -- skills
fi

# Decide invocation mode:
# - If a single argument is given and it directly contains subdirs (no SKILL.md/no *.md at top),
#   treat as parent mode and expand to immediate subdirs.
# - Otherwise treat each argument as an explicit skill dir.
targets=()
if [[ $# -eq 1 && -d "$1" && ! -f "$1/SKILL.md" ]]; then
  parent="${1%/}"
  for d in "$parent"/*/; do
    [[ -d "$d" ]] || continue
    targets+=("$d")
  done
  if [[ ${#targets[@]} -eq 0 ]]; then
    echo "No skill subdirs found under: $parent"
    exit 0
  fi
else
  for d in "$@"; do
    [[ -d "$d" ]] || { echo "Not a directory: $d"; exit 1; }
    targets+=("$d")
  done
fi

has_hangul=0

for dir in "${targets[@]}"; do
  name=$(basename "$dir")
  count=$( { grep -rPc '[가-힣]' "$dir" --include='*.md' --include='*.sh' 2>/dev/null || true; } | awk -F: '{s+=$2}END{print s+0}')

  if [[ "$count" -gt 0 ]]; then
    echo -e "${RED}✗${NC} $name — $count Korean lines found"
    # `head` may close early under `set -o pipefail`, producing SIGPIPE on `grep`;
    # `|| true` swallows that benign failure so the loop processes remaining dirs.
    { grep -rPn '[가-힣]' "$dir" --include='*.md' --include='*.sh' 2>/dev/null | head -5; } || true
    echo ""
    has_hangul=1
  else
    echo -e "${GREEN}✓${NC} $name — clean"
  fi
done

if [[ $has_hangul -eq 1 ]]; then
  echo -e "\n${RED}BLOCKED: Korean text found. Translate before publishing.${NC}"
  exit 1
fi

echo -e "\n${GREEN}All skills clean. Ready to publish.${NC}"
exit 0
