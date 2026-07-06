#!/usr/bin/env bash
# lint-frontmatter.sh — Verify each skill has a valid metadata.version.
# Usage: bash scripts/lint-frontmatter.sh [skills-dir]
#
# Checks per skills/<slug>/:
#   1. SKILL.md exists
#   2. metadata.version is a semver string in the form `version: "X.Y.Z"`
#      scoped to lines INSIDE the YAML `metadata:` block (top-level `version:`
#      or `version:` under other blocks is ignored).
#
# Convention: project enforces double-quoted version (current SKILL.md format).
# Unquoted YAML scalars (`version: 0.1.0`) are valid YAML but rejected here so
# the format is consistent across all skills.
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

# Extract `version: "X.Y.Z"` strictly from inside the YAML `metadata:` block.
# Prints the semver on success (one line), nothing on failure.
extract_metadata_version() {
  awk '
    BEGIN { in_fm=0; fm_seen=0; in_meta=0 }
    /^---[[:space:]]*$/ {
      if (fm_seen == 0) { in_fm = 1; fm_seen = 1; next }
      if (in_fm == 1)   { in_fm = 0; in_meta = 0; exit }
    }
    in_fm == 1 && /^metadata:[[:space:]]*$/ { in_meta = 1; next }
    in_fm == 1 && in_meta == 1 && /^[^[:space:]]/ { in_meta = 0 }
    in_fm == 1 && in_meta == 1 {
      # Match indented `version: "X.Y.Z"` (require double-quotes by project convention).
      # An optional trailing YAML comment is allowed so release-please annotations
      # like `# x-release-please-version` can sit on the same line.
      if (match($0, /^[[:space:]]+version:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"[[:space:]]*(#.*)?$/) > 0) {
        line = $0
        sub(/^[[:space:]]+version:[[:space:]]*"/, "", line)
        sub(/"[[:space:]]*(#.*)?$/, "", line)
        print line
        exit
      }
    }
  ' "$1"
}

# Detect a present-but-malformed version under metadata (used for better diagnostics).
diagnose_metadata_version() {
  awk '
    BEGIN { in_fm=0; fm_seen=0; in_meta=0; found=0 }
    /^---[[:space:]]*$/ {
      if (fm_seen == 0) { in_fm = 1; fm_seen = 1; next }
      if (in_fm == 1)   { in_fm = 0; in_meta = 0; exit }
    }
    in_fm == 1 && /^metadata:[[:space:]]*$/ { in_meta = 1; next }
    in_fm == 1 && in_meta == 1 && /^[^[:space:]]/ { in_meta = 0 }
    in_fm == 1 && in_meta == 1 && /^[[:space:]]+version:/ {
      print "  metadata.version line: " $0
      found = 1
    }
    END {
      if (found == 0) print "  (no version: key found inside metadata:)"
    }
  ' "$1"
}

exit_code=0

# Tracked-skill filter — mirrors check-hangul.py. Untracked local-only skills
# (in-development, personal, or not yet published) are exempt from this
# publish-time gate because they are not yet publishing surface.
declare -A TRACKED_SET=()
if tracked_out=$(git ls-files "$SKILLS_DIR" 2>/dev/null); then
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    # Strip the leading "$SKILLS_DIR/" prefix, then take the first path segment.
    case "$line" in
      "$SKILLS_DIR"/*) rel="${line#"$SKILLS_DIR"/}" ;;
      *)               continue ;;
    esac
    head="${rel%%/*}"
    [[ -n "$head" ]] && TRACKED_SET[$head]=1
  done <<< "$tracked_out"
fi
filter_active=0
[[ ${#TRACKED_SET[@]} -gt 0 ]] && filter_active=1

for dir in "$SKILLS_DIR"/*/; do
  [[ -d "$dir" ]] || continue
  name=$(basename "$dir")
  skill_md="$dir/SKILL.md"

  # Skip untracked skills when the filter is active. If git is unavailable or
  # nothing is tracked (fresh repo), fall back to scanning everything.
  if [[ $filter_active -eq 1 && -z "${TRACKED_SET[$name]:-}" ]]; then
    continue
  fi

  if [[ ! -f "$skill_md" ]]; then
    echo -e "${RED}✗${NC} $name — SKILL.md missing"
    exit_code=1
    continue
  fi

  version="$(extract_metadata_version "$skill_md" || true)"
  if [[ -z "$version" ]]; then
    echo -e "${RED}✗${NC} $name — metadata.version missing or invalid"
    echo '  Expected: `version: "X.Y.Z"` (double-quoted semver) inside the `metadata:` block'
    diagnose_metadata_version "$skill_md"
    exit_code=1
    continue
  fi

  echo -e "${GREEN}✓${NC} $name — v$version"
done

if [[ $exit_code -ne 0 ]]; then
  echo -e "\n${RED}BLOCKED: One or more skills failed frontmatter lint.${NC}"
fi

exit $exit_code
