#!/usr/bin/env bash
# check-hangul.sh — Verify no Korean text remains in skill directories before publishing.
# Usage: bash check-hangul.sh <skill-dir1> [skill-dir2] ...
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
  echo "Usage: $0 <skill-dir1> [skill-dir2] ..."
  exit 1
fi

has_hangul=0

for dir in "$@"; do
  name=$(basename "$dir")
  count=$( { grep -rPc '[가-힣]' "$dir" --include='*.md' --include='*.sh' 2>/dev/null || true; } | awk -F: '{s+=$2}END{print s+0}')

  if [[ "$count" -gt 0 ]]; then
    echo -e "${RED}✗${NC} $name — $count Korean lines found"
    grep -rPn '[가-힣]' "$dir" --include='*.md' --include='*.sh' 2>/dev/null | head -5
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
