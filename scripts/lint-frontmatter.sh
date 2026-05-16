#!/usr/bin/env bash
# lint-frontmatter.sh — Verify each skill has a valid metadata.version.
# Usage: bash scripts/lint-frontmatter.sh [skills-dir]
#
# Checks per skills/<slug>/:
#   1. SKILL.md exists
#   2. metadata.version is a semver string (e.g., "0.1.0")
#
# Note: LICENSE is a publish-time artifact (lives in the local skill dir,
# read by `clawhub publish <dir>`). It is intentionally NOT tracked in this
# repository, so LICENSE presence is not part of repo lint.
#
# Exit codes:
#   0 = all skills pass
#   1 = one or more failures

set -euo pipefail

SKILLS_DIR="${1:-skills}"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

if [[ ! -d "$SKILLS_DIR" ]]; then
  echo "Skills directory not found: $SKILLS_DIR"
  exit 1
fi

exit_code=0

for dir in "$SKILLS_DIR"/*/; do
  [[ -d "$dir" ]] || continue
  name=$(basename "$dir")
  skill_md="$dir/SKILL.md"

  if [[ ! -f "$skill_md" ]]; then
    echo -e "${RED}✗${NC} $name — SKILL.md missing"
    exit_code=1
    continue
  fi

  if ! grep -qE '^[[:space:]]*version:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "$skill_md"; then
    echo -e "${RED}✗${NC} $name — metadata.version missing or not semver"
    grep -nE 'version:' "$skill_md" | head -3 || true
    exit_code=1
    continue
  fi

  version=$(grep -oE 'version:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' "$skill_md" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
  echo -e "${GREEN}✓${NC} $name — v$version"
done

if [[ $exit_code -ne 0 ]]; then
  echo -e "\n${RED}BLOCKED: One or more skills failed frontmatter lint.${NC}"
fi

exit $exit_code
